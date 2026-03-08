import datetime as dt
import os
from typing import Any

import mlflow

MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow-service:5000")
mlflow.set_tracking_uri(MLFLOW_URI)


def log_inference(
    *,
    tenant_id: str,
    model_name: str,
    score: float,
    drift_score: float,
    metadata: dict[str, Any],
) -> None:
    with mlflow.start_run(run_name=f"{tenant_id}-{model_name}-{dt.datetime.utcnow().isoformat()}"):
        mlflow.log_param("tenant_id", tenant_id)
        mlflow.log_param("model_name", model_name)
        mlflow.log_metric("anomaly_score", score)
        mlflow.log_metric("drift_score", drift_score)
        for key, value in metadata.items():
            mlflow.set_tag(str(key), str(value))


def register_model_version(model_uri: str, model_name: str) -> str:
    result = mlflow.register_model(model_uri=model_uri, name=model_name)
    return str(result.version)


def should_trigger_retraining(drift_score: float, threshold: float = 0.25) -> bool:
    return drift_score >= threshold


def compute_drift_score(observed: list[float], expected: list[float]) -> float:
    if not observed or not expected or len(observed) != len(expected):
        return 0.0
    deltas = [abs(o - e) / max(abs(e), 1.0) for o, e in zip(observed, expected)]
    return round(sum(deltas) / len(deltas), 4)


def choose_canary_model(baseline_version: str, candidate_version: str, candidate_gain: float) -> str:
    if candidate_gain >= 0.03:
        return candidate_version
    return baseline_version

