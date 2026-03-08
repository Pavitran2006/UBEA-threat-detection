import datetime as dt
import json
import os

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr

try:
    from aiokafka import AIOKafkaProducer
except Exception:  # pragma: no cover
    AIOKafkaProducer = None

app = FastAPI(title="UEBA Login Event Ingestion")
producer: AIOKafkaProducer | None = None
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")


class LoginEvent(BaseModel):
    correlation_id: str
    user_id: int
    email: EmailStr
    ip_address: str
    device_fingerprint: str
    geo_location: str
    failed_login_attempts: int = 0
    previous_risk_score: float = 0.0
    authentication_status: str = "credentials_valid"


@app.on_event("startup")
async def startup_event() -> None:
    global producer
    if AIOKafkaProducer:
        producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await producer.start()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    if producer:
        await producer.stop()


@app.post("/ingest/login")
async def ingest_login(event: LoginEvent) -> dict[str, str]:
    if not producer:
        raise HTTPException(status_code=503, detail="Kafka producer unavailable")
    payload = event.dict()
    payload["login_timestamp"] = dt.datetime.utcnow().isoformat()
    await producer.send_and_wait("login_events", payload)
    return {"status": "event_ingested", "topic": "login_events"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8010)

