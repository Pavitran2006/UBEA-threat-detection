from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Tuple

import numpy as np
from sklearn.ensemble import IsolationForest
from sqlalchemy.orm import Session

from .models.user import User, LoginActivity, SecurityAlert, AnomalyScore


@dataclass
class UEBAFeatures:
    user_id: int
    login_frequency: float
    file_access: float
    failed_logins: float
    privilege_changes: float


def _window_start(days: int) -> datetime:
    return datetime.utcnow() - timedelta(days=days)


def build_feature_matrix(db: Session, days: int = 7) -> Tuple[np.ndarray, List[UEBAFeatures]]:
    users = db.query(User).all()
    feature_rows: List[UEBAFeatures] = []
    start = _window_start(days)

    for user in users:
        login_frequency = (
            db.query(LoginActivity)
            .filter(LoginActivity.user_id == user.id)
            .filter(LoginActivity.login_time >= start)
            .count()
        )
        failed_logins = (
            db.query(LoginActivity)
            .filter(LoginActivity.user_id == user.id)
            .filter(LoginActivity.activity_type == "login_failed")
            .filter(LoginActivity.login_time >= start)
            .count()
        )
        file_access = (
            db.query(SecurityAlert)
            .filter(SecurityAlert.user_id == user.id)
            .filter(SecurityAlert.alert_type.in_(["File Access", "Data Exfiltration"]))
            .filter(SecurityAlert.timestamp >= start)
            .count()
        )
        privilege_changes = (
            db.query(SecurityAlert)
            .filter(SecurityAlert.user_id == user.id)
            .filter(SecurityAlert.alert_type == "Privilege Escalation")
            .filter(SecurityAlert.timestamp >= start)
            .count()
        )

        feature_rows.append(
            UEBAFeatures(
                user_id=user.id,
                login_frequency=login_frequency,
                file_access=file_access,
                failed_logins=failed_logins,
                privilege_changes=privilege_changes,
            )
        )

    if not feature_rows:
        return np.zeros((0, 4)), []

    matrix = np.array(
        [
            [
                row.login_frequency,
                row.file_access,
                row.failed_logins,
                row.privilege_changes,
            ]
            for row in feature_rows
        ],
        dtype=float,
    )

    return matrix, feature_rows


def compute_anomaly_scores_from_db(db: Session, days: int = 7) -> List[dict]:
    matrix, rows = build_feature_matrix(db, days=days)
    if matrix.size == 0:
        return []

    model = IsolationForest(n_estimators=150, contamination=0.2, random_state=42)
    model.fit(matrix)
    raw_scores = -model.decision_function(matrix)

    min_score = float(np.min(raw_scores))
    max_score = float(np.max(raw_scores))
    if max_score - min_score == 0:
        normalized = [10 for _ in raw_scores]
    else:
        normalized = ((raw_scores - min_score) / (max_score - min_score)) * 100

    results = []
    for row, score in zip(rows, normalized):
        score_value = float(score)
        results.append({"user_id": row.user_id, "score": score_value})
        db.add(AnomalyScore(user_id=row.user_id, score=score_value))

    db.commit()
    return results


def get_latest_anomaly_score(db: Session, user_id: int) -> float | None:
    record = (
        db.query(AnomalyScore)
        .filter(AnomalyScore.user_id == user_id)
        .order_by(AnomalyScore.computed_at.desc())
        .first()
    )
    return float(record.score) if record else None


def compute_risk_score_from_db(db: Session, user_id: int) -> Tuple[int, str]:
    start = _window_start(7)
    anomaly_score = get_latest_anomaly_score(db, user_id)
    if anomaly_score is None:
        compute_anomaly_scores_from_db(db)
        anomaly_score = get_latest_anomaly_score(db, user_id) or random.uniform(10, 40)

    failed_logins = (
        db.query(LoginActivity)
        .filter(LoginActivity.user_id == user_id)
        .filter(LoginActivity.activity_type == "login_failed")
        .filter(LoginActivity.login_time >= start)
        .count()
    )
    file_access = (
        db.query(SecurityAlert)
        .filter(SecurityAlert.user_id == user_id)
        .filter(SecurityAlert.alert_type.in_(["File Access", "Data Exfiltration"]))
        .filter(SecurityAlert.timestamp >= start)
        .count()
    )

    score = min(100, int(anomaly_score + failed_logins * 5 + file_access * 3))

    if score <= 30:
        level = "Low"
    elif score <= 70:
        level = "Medium"
    else:
        level = "High"

    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.risk_score = score
        db.commit()

    return score, level
