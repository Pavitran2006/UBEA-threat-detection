from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RiskSignal:
    is_new_device: bool = False
    is_new_location: bool = False
    failed_attempts: int = 0
    ip_reputation_score: float = 0.0
    login_hour: int | None = None


def calculate_risk_score(signal: RiskSignal) -> float:
    score = 0.0

    if signal.is_new_device:
        score += 18.0
    if signal.is_new_location:
        score += 22.0

    score += min(signal.failed_attempts * 5.0, 25.0)
    score += max(min(signal.ip_reputation_score, 25.0), 0.0)

    if signal.login_hour is not None:
        if signal.login_hour < 6 or signal.login_hour > 22:
            score += 10.0

    return min(score, 100.0)


def summarize_risk(score: float) -> str:
    if score >= 75:
        return "Critical"
    if score >= 50:
        return "High"
    if score >= 25:
        return "Medium"
    return "Low"
