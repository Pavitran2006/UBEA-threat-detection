from typing import Literal

DecisionStatus = Literal["allowed", "2fa_required", "blocked"]


def decision_from_risk(risk_score: float) -> DecisionStatus:
    if risk_score < 40:
        return "allowed"
    if risk_score <= 70:
        return "2fa_required"
    return "blocked"

