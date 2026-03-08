from __future__ import annotations

import math


def compute_risk_score(
    *,
    previous_risk_score: float,
    anomaly_score: float,
    failed_login_attempts: int,
    elapsed_hours_since_last_login: float,
    decay_per_hour: float = 0.8,
) -> float:
    decayed_risk = max(0.0, previous_risk_score - (elapsed_hours_since_last_login * decay_per_hour))

    # Failed attempts use logarithmic scaling to avoid unbounded growth.
    failed_attempt_component = min(30.0, math.log1p(max(0, failed_login_attempts)) * 10.0)

    final_score = decayed_risk * 0.65 + anomaly_score * 0.3 + failed_attempt_component * 0.05
    return max(0.0, min(100.0, round(final_score, 2)))

