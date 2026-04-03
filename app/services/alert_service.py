from sqlalchemy.orm import Session
from app.models import SecurityAlert
from datetime import datetime

class AlertService:
    @staticmethod
    def generate_risk_alert(db: Session, user_id: int, risk_score: float, ip_address: str, reason: str = ""):
        """
        Creates a SecurityAlert if the risk score exceeds threshold (50).
        """
        if risk_score > 50:
            severity = "Critical" if risk_score > 80 else "High"
            
            alert_type = "Suspicious Login"
            if "Multiple login attempts" in reason:
                alert_type = "Multiple Login Attempts"
                
            desc = f"Login risk score calculated at {risk_score:.1f}. Reasons: {reason}".strip()
            
            alert = SecurityAlert(
                user_id=user_id,
                alert_type=alert_type,
                severity=severity,
                description=desc,
                ip_address=ip_address,
                timestamp=datetime.utcnow()
            )
            db.add(alert)
            db.commit()
            return alert
        return None
