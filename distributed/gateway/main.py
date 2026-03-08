from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Security
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from shared.kafka_utils import KafkaManager
import asyncio
import os
import json
from elasticsearch import AsyncElasticsearch
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from shared.kafka_utils import KafkaManager
from shared.auth_utils import AuthHandler, TokenBlacklist
import uuid
import datetime
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

# Metrics
REQUEST_COUNT = Counter('gateway_requests_total', 'Total requests to Gateway', ['endpoint', 'status', 'tenant_id'])
ACTIVE_RISK = Gauge('user_risk_score', 'Real-time user risk score', ['user_id', 'tenant_id'])

app = FastAPI(title="UEBA Gateway Service")
templates = Jinja2Templates(directory="templates")

ELASTICSEARCH_URL = os.getenv('ELASTICSEARCH_URL', 'http://localhost:9200')
DATABASE_URL = os.getenv('DATABASE_URL', 'mysql+pymysql://root:password@localhost/ueba_db')

es = AsyncElasticsearch([ELASTICSEARCH_URL])
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserRisk(Base):
    __tablename__ = "user_risks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True)
    username = Column(String(50))
    risk_score = Column(Float)

# Registry to track pending login decisions
class DecisionRegistry:
    def __init__(self):
        self.pending = {}

    def add(self, correlation_id):
        future = asyncio.get_event_loop().create_future()
        self.pending[correlation_id] = future
        return future

    def set_result(self, correlation_id, result):
        if correlation_id in self.pending:
            self.pending[correlation_id].set_result(result)
            del self.pending[correlation_id]

decision_registry = DecisionRegistry()

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
async def health_check():
    health = {"status": "healthy", "checks": {}}
    
    # 1. Check DB
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        health["checks"]["database"] = "up"
    except Exception as e:
        health["status"] = "degraded"
        health["checks"]["database"] = f"down: {str(e)}"

    # 2. Check Elasticsearch
    try:
        await es.ping()
        health["checks"]["elasticsearch"] = "up"
    except Exception as e:
        health["status"] = "degraded"
        health["checks"]["elasticsearch"] = f"down: {str(e)}"

    return health

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    REQUEST_COUNT.labels(endpoint='/', status='200', tenant_id='default').inc()
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/dashboard/stats")
async def get_stats():
    db = SessionLocal()
    total_users = db.query(UserRisk).count()
    users = db.query(UserRisk).all()
    user_data = [{"username": u.username, "score": u.risk_score} for u in users]
    db.close()
    
    # Get total alerts from ES
    resp = await es.count(index="ueba-anomalies")
    total_alerts = resp['count']
    
    return {
        "total_users": total_users,
        "total_alerts": total_alerts,
        "users": user_data
    }

@app.get("/api/dashboard/alerts")
async def get_alerts():
    resp = await es.search(index="ueba-anomalies", query={"match_all": {}}, size=20, sort=[{"timestamp": "desc"}])
    alerts = [hit['_source'] for hit in resp['hits']['hits']]
    return alerts

@app.post("/api/auth/login")
async def login(request: Request):
    data = await request.json()
    email = data.get("email")
    password = data.get("password")
    
    # 1. Basic validation (Mocking DB lookup for this example)
    # In production, lookup user in DB, check password hash
    mock_user = {"id": 1, "username": "admin", "email": email, "role": "admin"}
    mock_user = {"id": 1, "username": "admin", "email": email, "role": "admin", "tenant_id": "default_tenant"} # Added tenant_id to mock_user
    
    correlation_id = str(uuid.uuid4())
    
    # 2. Collect fingerprinting data
    login_event = {
        "correlation_id": correlation_id,
        "tenant_id": mock_user["tenant_id"], # Propagate tenant_id
        "user_id": mock_user["id"],
        "email": email,
        "ip_address": request.client.host,
        "device_fingerprint": request.headers.get("User-Agent", "unknown"), # Use User-Agent from headers
        "login_timestamp": datetime.datetime.utcnow().isoformat(),
    }
    
    # 3. Publish to Kafka
    producer = await KafkaManager.get_producer()
    await producer.send_and_wait("login_events", login_event)
    await producer.stop()
    
    # 4. Wait for decision (Adaptive Auth)
    decision_future = decision_registry.add(correlation_id)
    try:
        # Wait up to 5 seconds for decision engine
        decision = await asyncio.wait_for(decision_future, timeout=5.0)
    except asyncio.TimeoutError:
        # Fallback to 2FA if engine is slow / unreachable (Fail-safe)
        decision = {"status": "2fa_required", "risk_score": 50}

    # 5. Handle decision
    response_data = {"status": decision["status"], "risk_score": decision["risk_score"]}
    
    if decision["status"] == "allowed":
        access_token = AuthHandler.create_access_token(data={"sub": email, "role": mock_user["role"]})
        refresh_token = AuthHandler.create_refresh_token(email=email)
        
        from fastapi.responses import JSONResponse
        content = {"status": "allowed", "message": "Login successful"}
        response = JSONResponse(content=content)
        
        # Set HTTP-only secure cookies
        response.set_cookie(
            key="access_token", 
            value=access_token, 
            httponly=True, 
            secure=True, 
            samesite="lax",
            max_age=3600
        )
        response.set_cookie(
            key="refresh_token", 
            value=refresh_token, 
            httponly=True, 
            secure=True, 
            samesite="lax",
            max_age=604800
        )
        return response
        
    return response_data

@app.post("/api/session-event")
async def session_event(request: Request, user: dict = Security(AuthHandler.get_current_user)):
    data = await request.json()
    
    # Enrich event with user context
    event = {
        "tenant_id": user["tenant_id"],
        "user_id": user["sub"],
        "role": user["role"],
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "ip_address": request.client.host,
        "behavior": data
    }
    
    # Publish to session_events
    producer = await KafkaManager.get_producer()
    await producer.send_and_wait("session_events", event)
    await producer.stop()
    
    return {"status": "received"}

async def listen_decisions():
    """Background task to listen for auth and session decisions from Kafka"""
    # Listen to both auth_decisions and session_invalidation
    consumer = await KafkaManager.get_consumer(["auth_decisions", "session_invalidation"], "gateway-decision-group")
    try:
        async for msg in consumer:
            data = msg.value
            if msg.topic == "auth_decisions":
                decision_registry.set_result(data["correlation_id"], data)
            elif msg.topic == "session_invalidation":
                # Invalidate individual session (if token tracking is implemented)
                # For this demo, we'll blacklist common identifiers or just log
                print(f"[GATEWAY] Invaliding session for user: {data.get('user_id')}")
                # Note: In a real system, we'd need the specific JTI or token to blacklist
    finally:
        await consumer.stop()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(listen_decisions())

@app.websocket("/ws/risk")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    consumer = await KafkaManager.get_consumer("risk_updates", "gateway-group")
    try:
        async for msg in consumer:
            await websocket.send_json(msg.value)
    except WebSocketDisconnect:
        await consumer.stop()
    except Exception as e:
        print(f"WS Error: {e}")
        await consumer.stop()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
