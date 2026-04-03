from sqlalchemy.orm import Session
from app.models import User
from datetime import datetime

class RiskEngine:
    @staticmethod
    def haversine_distance(lat1, lon1, lat2, lon2) -> float:
        """Calculate the great circle distance between two points in km."""
        import math
        R = 6371.0  # Earth radius in km
        
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat / 2)**2 + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlon / 2)**2)
        c = 2 * math.asin(math.sqrt(a))
        return R * c

    @staticmethod
    def calculate_risk(db: Session, user: User, current_activity: dict) -> tuple[float, list[str]]:
        """
        Calculate login risk based on:
        * New location -> +30
        * New device -> +20
        * Login at unusual time (late night) -> +10
        * Multiple logins in short time -> +20
        """
        risk_score = 0.0
        reasons = []

        now = datetime.utcnow()
        from datetime import timedelta
        from app.models import Activity
        
        # 1. Unusual Time (Late night: 00:00 - 05:00)
        if 0 <= now.hour < 5:
            risk_score += 10
            reasons.append("Login at unusual time (late night).")
            
        # 2. Multiple logins in a short time (e.g. less than 15 mins)
        fifteen_minutes_ago = now - timedelta(minutes=15)
        recent_logins = db.query(Activity).filter(
            Activity.user_id == user.id,
            Activity.login_time >= fifteen_minutes_ago
        ).count()
        # if >= 2, we consider it multiple logins
        if recent_logins >= 2:
            risk_score += 20
            reasons.append("Multiple login attempts detected.")
            
        # Fetch past activities to compare device and location
        past_activities = db.query(Activity).filter(
            Activity.user_id == user.id,
            Activity.status == 'success',
            Activity.ip_address.isnot(None)
        ).order_by(Activity.login_time.desc()).limit(20).all()

        if past_activities:
            # 3. New Device
            known_devices = {a.device for a in past_activities if a.device}
            if current_activity.get('device') and current_activity.get('device') != "Unknown" and current_activity.get('device') not in known_devices:
                risk_score += 20
                reasons.append(f"Login from new device: {current_activity.get('device')}.")

            # 4. New Location
            known_countries = {a.country for a in past_activities if a.country}
            known_cities = {a.city for a in past_activities if a.city}
            
            if current_activity.get('country') and current_activity.get('country') != "Unknown" and current_activity.get('country') not in known_countries:
                risk_score += 30
                reasons.append(f"Suspicious login from new country: {current_activity.get('country')}.")
            elif current_activity.get('city') and current_activity.get('city') != "Unknown" and current_activity.get('city') not in known_cities:
                risk_score += 15 # City change is less risky than country but still noted
                reasons.append(f"Login from new city: {current_activity.get('city')}.")

        # Clamp max
        risk_score = min(100.0, risk_score)
        return risk_score, reasons
