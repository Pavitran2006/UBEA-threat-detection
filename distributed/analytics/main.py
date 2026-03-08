import asyncio
import datetime as dt
import json
import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
import uvicorn
from fastapi import FastAPI
from sklearn.ensemble import IsolationForest
from distributed.analytics.mlops import (
    compute_drift_score,
    log_inference,
    should_trigger_retraining,
    choose_canary_model,
)

try:
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
except Exception:  # pragma: no cover
    AIOKafkaConsumer = None
    AIOKafkaProducer = None

try:
    from elasticsearch import AsyncElasticsearch
except Exception:  # pragma: no cover
    AsyncElasticsearch = None

app = FastAPI(title="UEBA Continuous Analytics Service")
logger = logging.getLogger("continuous-analytics")
logging.basicConfig(level=logging.INFO)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
BASELINE_FILE = Path(os.getenv("BASELINE_STORE_FILE", "distributed/analytics/baselines.json"))

_producer: AIOKafkaProducer | None = None
_consumer_task: asyncio.Task | None = None
_es = AsyncElasticsearch([ELASTICSEARCH_URL]) if AsyncElasticsearch else None

_login_model = IsolationForest(n_estimators=200, contamination=0.05, random_state=42)
_login_model.fit(np.random.rand(500, 4))

BASELINES: dict[str, dict[str, float]] = {}


def _load_baselines() -> None:
    global BASELINES
    if BASELINE_FILE.exists():
        try:
            BASELINES = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed loading baseline file; initializing empty store")
            BASELINES = {}


def _save_baselines() -> None:
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(json.dumps(BASELINES, indent=2), encoding="utf-8")


def _get_or_create_baseline(tenant_id: str, user_id: int) -> dict[str, float]:
    key = f"{tenant_id}:{user_id}"
    if key not in BASELINES:
        BASELINES[key] = {
            "mouse_movement_frequency": 20.0,
            "click_rate": 6.0,
            "api_request_frequency": 8.0,
            "page_navigation_timing_ms": 3000.0,
            "samples": 0.0,
        }
    return BASELINES[key]


def _update_baseline(baseline: dict[str, float], event: dict[str, Any], alpha: float = 0.08) -> None:
    for key in (
        "mouse_movement_frequency",
        "click_rate",
        "api_request_frequency",
        "page_navigation_timing_ms",
    ):
        observed = float(event.get(key, 0.0))
        baseline[key] = (1 - alpha) * float(baseline.get(key, observed)) + alpha * observed
    baseline["samples"] = float(baseline.get("samples", 0.0)) + 1.0


def _login_feature_vector(event: dict[str, Any]) -> np.ndarray:
    timestamp_raw = event.get("login_timestamp")
    parsed = dt.datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00")) if timestamp_raw else dt.datetime.utcnow()
    hour = parsed.hour / 23.0
    weekday = parsed.weekday() / 6.0
    ip_hash = (hash(event.get("ip_address", "")) % 1000) / 1000.0
    device_hash = (hash(event.get("device_fingerprint", "")) % 1000) / 1000.0
    return np.array([[hour, weekday, ip_hash, device_hash]])


def _session_anomaly_score(event: dict[str, Any], baseline: dict[str, float]) -> float:
    observed = np.array(
        [
            float(event.get("mouse_movement_frequency", 0.0)),
            float(event.get("click_rate", 0.0)),
            float(event.get("api_request_frequency", 0.0)),
            float(event.get("page_navigation_timing_ms", 0.0)),
        ]
    )
    expected = np.array(
        [
            float(baseline.get("mouse_movement_frequency", 1.0)),
            float(baseline.get("click_rate", 1.0)),
            float(baseline.get("api_request_frequency", 1.0)),
            float(baseline.get("page_navigation_timing_ms", 1.0)),
        ]
    )
    # normalized deviation
    deviation = np.abs(observed - expected) / np.maximum(expected, 1.0)
    score = min(100.0, float(np.mean(deviation) * 100.0))
    return round(score, 2)


async def _index(index: str, doc: dict[str, Any]) -> None:
    if not _es:
        return
    try:
        await _es.index(index=index, document=doc)
    except Exception:
        logger.exception("Failed indexing document to Elasticsearch")


async def _publish(topic: str, payload: dict[str, Any]) -> None:
    if _producer:
        await _producer.send_and_wait(topic, payload)


async def _process_login_event(event: dict[str, Any]) -> None:
    features = _login_feature_vector(event)
    model_score = float(_login_model.decision_function(features)[0])
    anomaly_score = max(0.0, min(100.0, round(abs(model_score) * 100.0, 2)))
    anomaly_event = {
        "correlation_id": event.get("correlation_id"),
        "user_id": event.get("user_id"),
        "tenant_id": event.get("tenant_id", "default"),
        "email": event.get("email"),
        "anomaly_score": anomaly_score,
        "model_score": model_score,
        "timestamp": dt.datetime.utcnow().isoformat(),
    }
    tenant_id = str(event.get("tenant_id", "default"))
    drift_score = compute_drift_score(
        observed=[float(features[0][0]), float(features[0][1]), float(features[0][2]), float(features[0][3])],
        expected=[0.5, 0.5, 0.5, 0.5],
    )
    log_inference(
        tenant_id=tenant_id,
        model_name=f"login-iforest-{tenant_id}",
        score=anomaly_score,
        drift_score=drift_score,
        metadata={"pipeline": "login", "correlation_id": event.get("correlation_id")},
    )
    anomaly_event["drift_score"] = drift_score
    anomaly_event["retraining_triggered"] = should_trigger_retraining(drift_score)
    anomaly_event["canary_model_version"] = choose_canary_model("v1", "v2", 0.04 if drift_score > 0.3 else 0.0)
    await _index("adaptive-login-anomalies", anomaly_event)
    await _publish("anomaly_events", anomaly_event)


async def _process_session_event(event: dict[str, Any]) -> None:
    user_id = int(event.get("user_id", -1))
    tenant_id = str(event.get("tenant_id", "default"))
    if user_id < 0:
        return
    baseline = _get_or_create_baseline(tenant_id, user_id)
    score = _session_anomaly_score(event, baseline)
    drift_score = compute_drift_score(
        observed=[
            float(event.get("mouse_movement_frequency", 0.0)),
            float(event.get("click_rate", 0.0)),
            float(event.get("api_request_frequency", 0.0)),
            float(event.get("page_navigation_timing_ms", 0.0)),
        ],
        expected=[
            float(baseline.get("mouse_movement_frequency", 0.0)),
            float(baseline.get("click_rate", 0.0)),
            float(baseline.get("api_request_frequency", 0.0)),
            float(baseline.get("page_navigation_timing_ms", 0.0)),
        ],
    )
    _update_baseline(baseline, event)
    _save_baselines()
    log_inference(
        tenant_id=tenant_id,
        model_name=f"session-behavior-{tenant_id}",
        score=score,
        drift_score=drift_score,
        metadata={"pipeline": "session", "page_path": event.get("page_path", "/")},
    )

    anomaly_event = {
        "correlation_id": event.get("correlation_id"),
        "user_id": user_id,
        "tenant_id": tenant_id,
        "email": event.get("email"),
        "session_anomaly_score": score,
        "drift_score": drift_score,
        "retraining_triggered": should_trigger_retraining(drift_score),
        "failed_api_attempts": int(event.get("failed_api_attempts", 0)),
        "timestamp": dt.datetime.utcnow().isoformat(),
    }
    await _index("adaptive-session-anomalies", anomaly_event)
    await _publish("session_anomaly_events", anomaly_event)


async def _consume_topics() -> None:
    if AIOKafkaConsumer is None:
        logger.warning("aiokafka unavailable. Analytics consumer not started.")
        return
    consumer = AIOKafkaConsumer(
        "login_events",
        "session_events",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="continuous-analytics-group",
        auto_offset_reset="latest",
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
    )
    await consumer.start()
    logger.info("Continuous analytics consuming login_events and session_events")
    try:
        async for msg in consumer:
            try:
                if msg.topic == "login_events":
                    await _process_login_event(msg.value)
                elif msg.topic == "session_events":
                    await _process_session_event(msg.value)
            except Exception:
                logger.exception("Failed processing event from %s", msg.topic)
    finally:
        await consumer.stop()


@app.on_event("startup")
async def startup() -> None:
    global _producer, _consumer_task
    _load_baselines()
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
    return {"status": "healthy", "service": "continuous-analytics"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8011)
