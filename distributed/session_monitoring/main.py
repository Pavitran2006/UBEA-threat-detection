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

app = FastAPI(title="UEBA Session Monitoring Ingestion Service")
producer: AIOKafkaProducer | None = None
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")


class SessionEventPayload(BaseModel):
    correlation_id: str
    user_id: int
    email: EmailStr
    ip_address: str
    mouse_movement_frequency: int
    click_rate: int
    api_request_frequency: int
    failed_api_attempts: int = 0
    page_navigation_timing_ms: float
    page_path: str


@app.on_event("startup")
async def startup() -> None:
    global producer
    if AIOKafkaProducer:
        producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda x: json.dumps(x).encode("utf-8"),
        )
        await producer.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    if producer:
        await producer.stop()


@app.post("/api/session-event")
async def ingest_session_event(payload: SessionEventPayload) -> dict[str, str]:
    if not producer:
        raise HTTPException(status_code=503, detail="Kafka producer unavailable")
    event = payload.dict()
    event["captured_at"] = dt.datetime.utcnow().isoformat()
    await producer.send_and_wait("session_events", event)
    return {"status": "accepted", "topic": "session_events"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "session-monitoring"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8013)

