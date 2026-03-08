import asyncio
import datetime as dt
import json
import logging
import os
from typing import Any

import math
import uvicorn
from fastapi import FastAPI

try:
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
except Exception:  # pragma: no cover
    AIOKafkaConsumer = None
    AIOKafkaProducer = None

try:
    from elasticsearch import AsyncElasticsearch
except Exception:  # pragma: no cover
    AsyncElasticsearch = None

app = FastAPI(title="UEBA Adaptive Risk Engine")
logger = logging.getLogger("adaptive-risk")
logging.basicConfig(level=logging.INFO)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
LOCK_DURATION_MINUTES = int(os.getenv("ACCOUNT_LOCK_MINUTES", "15"))

_producer: AIOKafkaProducer | None = None
_login_state: dict[str, dict[str, Any]] = {}
_risk_state: dict[str, dict[str, Any]] = {}
_consumer_task: asyncio.Task | None = None
_es = AsyncElasticsearch([ELASTICSEARCH_URL]) if AsyncElasticsearch else None


def decision_from_risk(risk_score: float) -> str:
    if risk_score < 40:
        return "allowed"
    if risk_score <= 70:
        return "2fa_required"
    return "blocked"


def compute_risk_score(
    *,
    previous_risk_score: float,
    anomaly_score: float,
    failed_login_attempts: int,
    elapsed_hours_since_last_login: float,
    decay_per_hour: float = 0.8,
) -> float:
    decayed_risk = max(0.0, previous_risk_score - (elapsed_hours_since_last_login * decay_per_hour))
    failed_attempt_component = min(30.0, math.log1p(max(0, failed_login_attempts)) * 10.0)
    final_score = decayed_risk * 0.65 + anomaly_score * 0.3 + failed_attempt_component * 0.05
    return max(0.0, min(100.0, round(final_score, 2)))


def _risk_key(tenant_id: str, user_id: int) -> str:
    return f"{tenant_id}:{user_id}"


def _get_previous_risk(tenant_id: str, user_id: int) -> tuple[float, float]:
    state = _risk_state.get(_risk_key(tenant_id, user_id))
    if not state:
        return 0.0, 1.0
    last_update = state.get("updated_at", dt.datetime.utcnow())
    elapsed_hours = max(0.0, (dt.datetime.utcnow() - last_update).total_seconds() / 3600.0)
    return float(state.get("risk_score", 0.0)), elapsed_hours


async def _publish_risk_update(update: dict[str, Any]) -> None:
    if _producer:
        await _producer.send_and_wait("risk_updates", update)


async def _publish(topic: str, payload: dict[str, Any]) -> None:
    if _producer:
        await _producer.send_and_wait(topic, payload)


async def _index_threat(payload: dict[str, Any]) -> None:
    if not _es:
        return
    try:
        await _es.index(index="active-threat-sessions", document=payload)
    except Exception:
        logger.exception("Failed to index active threat event")


async def _emit_session_security_actions(
    *,
    tenant_id: str,
    user_id: int,
    email: str,
    risk_score: float,
    source: str,
) -> None:
    now = dt.datetime.utcnow()
    if risk_score > 60:
        invalidation = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "email": email,
            "risk_score": risk_score,
            "reason": "session_risk_threshold_exceeded",
            "source": source,
            "timestamp": now.isoformat(),
        }
        await _publish("session_invalidation", invalidation)
        await _index_threat({"event": "session_invalidation", **invalidation})

    if risk_score > 80:
        lock_until = now + dt.timedelta(minutes=LOCK_DURATION_MINUTES)
        lock_event = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "email": email,
            "risk_score": risk_score,
            "reason": "critical_session_risk",
            "source": source,
            "timestamp": now.isoformat(),
            "lock_until": lock_until.isoformat(),
        }
        await _publish("account_lock", lock_event)
        await _index_threat({"event": "account_lock", **lock_event})


async def _calculate_and_publish(correlation_id: str) -> None:
    context = _login_state.get(correlation_id)
    if not context:
        return
    user_id = int(context.get("user_id", -1))
    tenant_id = str(context.get("tenant_id", "default"))
    if user_id < 0:
        return

    prev_risk, elapsed_hours = _get_previous_risk(tenant_id, user_id)
    anomaly_score = float(context.get("anomaly_score", 0.0))
    failed_attempts = int(context.get("failed_login_attempts", 0))

    risk_score = compute_risk_score(
        previous_risk_score=prev_risk,
        anomaly_score=anomaly_score,
        failed_login_attempts=failed_attempts,
        elapsed_hours_since_last_login=elapsed_hours,
    )
    status = decision_from_risk(risk_score)

    _risk_state[_risk_key(tenant_id, user_id)] = {"risk_score": risk_score, "updated_at": dt.datetime.utcnow()}
    update = {
        "correlation_id": correlation_id,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "email": context.get("email"),
        "risk_score": risk_score,
        "status": status,
        "failed_login_attempts": failed_attempts,
        "anomaly_score": anomaly_score,
        "timestamp": dt.datetime.utcnow().isoformat(),
    }
    await _publish_risk_update(update)
    await _emit_session_security_actions(
        tenant_id=tenant_id,
        user_id=user_id,
        email=context.get("email", ""),
        risk_score=risk_score,
        source="login_auth",
    )
    _login_state.pop(correlation_id, None)


async def _update_session_risk(event: dict[str, Any]) -> None:
    user_id = int(event.get("user_id", -1))
    tenant_id = str(event.get("tenant_id", "default"))
    if user_id < 0:
        return
    email = str(event.get("email", ""))
    session_anomaly_score = float(event.get("session_anomaly_score", 0.0))
    failed_api_attempts = int(event.get("failed_api_attempts", 0))

    prev_risk, elapsed_hours = _get_previous_risk(tenant_id, user_id)
    combined_anomaly = min(100.0, session_anomaly_score + failed_api_attempts * 4.0)
    session_risk = compute_risk_score(
        previous_risk_score=prev_risk,
        anomaly_score=combined_anomaly,
        failed_login_attempts=failed_api_attempts,
        elapsed_hours_since_last_login=elapsed_hours,
    )
    status = decision_from_risk(session_risk)
    _risk_state[_risk_key(tenant_id, user_id)] = {"risk_score": session_risk, "updated_at": dt.datetime.utcnow()}

    update = {
        "correlation_id": event.get("correlation_id"),
        "user_id": user_id,
        "tenant_id": tenant_id,
        "email": email,
        "risk_score": session_risk,
        "status": status,
        "session_anomaly_score": session_anomaly_score,
        "failed_api_attempts": failed_api_attempts,
        "timestamp": dt.datetime.utcnow().isoformat(),
        "source": "session_monitoring",
    }
    await _publish_risk_update(update)
    await _emit_session_security_actions(
        tenant_id=tenant_id,
        user_id=user_id,
        email=email,
        risk_score=session_risk,
        source="session_monitoring",
    )


async def _consume_topics() -> None:
    if AIOKafkaConsumer is None:
        logger.warning("aiokafka unavailable. Risk engine consumer not started.")
        return

    login_consumer = AIOKafkaConsumer(
        "login_events",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="adaptive-risk-group-login",
        auto_offset_reset="latest",
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
    )
    anomaly_consumer = AIOKafkaConsumer(
        "anomaly_events",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="adaptive-risk-group-anomaly",
        auto_offset_reset="latest",
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
    )
    session_anomaly_consumer = AIOKafkaConsumer(
        "session_anomaly_events",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="adaptive-risk-group-session-anomaly",
        auto_offset_reset="latest",
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
    )
    await login_consumer.start()
    await anomaly_consumer.start()
    await session_anomaly_consumer.start()
    logger.info("Adaptive risk engine consuming login_events, anomaly_events, session_anomaly_events")

    async def login_loop() -> None:
        async for msg in login_consumer:
            event = msg.value
            correlation_id = event.get("correlation_id")
            if not correlation_id:
                continue
            _login_state[correlation_id] = event
            if event.get("authentication_status") == "failed":
                _login_state[correlation_id]["anomaly_score"] = 0.0
                await _calculate_and_publish(correlation_id)

    async def anomaly_loop() -> None:
        async for msg in anomaly_consumer:
            event = msg.value
            correlation_id = event.get("correlation_id")
            if not correlation_id:
                continue
            if correlation_id not in _login_state:
                _login_state[correlation_id] = {}
            _login_state[correlation_id]["anomaly_score"] = float(event.get("anomaly_score", 0.0))
            await _calculate_and_publish(correlation_id)

    async def session_anomaly_loop() -> None:
        async for msg in session_anomaly_consumer:
            event = msg.value
            await _update_session_risk(event)

    try:
        await asyncio.gather(login_loop(), anomaly_loop(), session_anomaly_loop())
    finally:
        await login_consumer.stop()
        await anomaly_consumer.stop()
        await session_anomaly_consumer.stop()


@app.on_event("startup")
async def startup() -> None:
    global _producer, _consumer_task
    if AIOKafkaProducer:
        _producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda x: json.dumps(x).encode("utf-8"),
        )
        await _producer.start()
    _consumer_task = asyncio.create_task(_consume_topics())


@app.on_event("shutdown")
async def shutdown() -> None:
    if _consumer_task:
        _consumer_task.cancel()
    if _producer:
        await _producer.stop()
    if _es:
        await _es.close()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "adaptive-risk-engine"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8012)
