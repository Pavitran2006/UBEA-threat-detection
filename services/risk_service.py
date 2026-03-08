from app.models import User, Activity, Alert
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class RiskService:
    @staticmethod
    def calculate_user_risk(db, user_id):
        """
        Calculates and updates the cumulative risk score for a user.
        Includes weighted anomalies, contextual triggers, and temporal decay.
        """
        try:
            user = db.query(User).get(user_id)
            if not user:
                return None

            # 1. Apply Temporal Decay (10% per 24 hours of normal behavior)
            time_now = datetime.utcnow()
            time_diff = time_now - user.created_at
            days_passed = time_diff.total_seconds() / (24 * 3600)
            
            if days_passed > 0:
                # Decay formula: Score = Score * (0.9 ^ days)
                decay_factor = 0.9 ** days_passed
                user.risk_score *= decay_factor

            # 2. Base Score from Anomaly Detections (Recent)
            # We look at alerts in the last 7 days for current risk
            recent_alerts = db.query(Alert).filter(
                Alert.user_id == user_id,
                Alert.detected_at >= (time_now - timedelta(days=7))
            ).all()

            alert_weight = 0
            for alert in recent_alerts:
                if alert.risk_level == 'High': alert_weight += 5
                elif alert.risk_level == 'Medium': alert_weight += 3
                else: alert_weight += 1

            # 3. Contextual Weighting (From latest activity)
            latest_activity = db.query(Activity).filter_by(user_id=user_id).order_by(Activity.login_time.desc()).first()
            context_weight = 0
            
            if latest_activity:
                # Unusual Hour (e.g., 00:00 - 05:00)
                if 0 <= latest_activity.login_time.hour <= 5:
                    context_weight += 2
                
                # New IP check (Simplified: check if this IP appeared before for this user)
                ip_count = db.query(Activity).filter_by(user_id=user_id, ip_address=latest_activity.ip_address).count()
                if ip_count == 1: # First time this IP is seen
                    context_weight += 3

            # 4. Aggregate & Update
            # We add current weights to the decayed base score
            # Note: We cap the risk score for presentation
            new_score = user.risk_score + alert_weight + context_weight
            user.risk_score = min(max(new_score, 0), 100)
            
            db.commit()
            return user.risk_score

        except Exception as e:
            logger.error(f"Error calculating risk for user {user_id}: {str(e)}")
            db.rollback()
            return None

    @staticmethod
    def get_risk_classification(score):
        """Categorizes the score into a human-readable level."""
        if score > 60: return "Critical"
        if score > 30: return "High"
        if score > 10: return "Medium"
        return "Low"
