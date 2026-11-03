import logging
import hashlib
from datetime import datetime, timedelta
import pandas as pd
from sklearn.ensemble import IsolationForest
from sqlalchemy.orm import Session
from app.models import Activity, Alert

logger = logging.getLogger("ueba.anomaly")

class AnomalyDetector:
    def __init__(self):
        # IsolationForest to detect structural outliers in login behavior
        self.model = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
        
    def _extract_features(self, activities):
        """Convert a list of models.Activity into a pandas DataFrame suitable for IsolationForest."""
        data = []
        def stable_hash(s):
            return int(hashlib.md5(str(s or "Unknown").encode()).hexdigest(), 16) % 1000

        for i, act in enumerate(activities):
            t = act.login_time or datetime.utcnow()
            hour = t.hour
            weekday = t.weekday()
            
            # Frequency: time since last login in hours
            if i > 0:
                prev_t = activities[i-1].login_time or t
                time_diff = max(0.0, (t - prev_t).total_seconds() / 3600.0)
            else:
                time_diff = 0.0
            
            loc_code = stable_hash(act.country)
            dev_code = stable_hash(act.device)
            
            data.append({
                'hour': hour,
                'weekday': weekday,
                'frequency': time_diff,
                'location_code': loc_code,
                'device_code': dev_code
            })
            
        return pd.DataFrame(data)

    def train_and_detect(self, db: Session, user_id: int):
        """Train the model on the user's historical data and detect if recent activities are anomalies."""
        try:
            # Fetch user's history
            activities = db.query(Activity).filter(Activity.user_id == user_id).order_by(Activity.login_time.asc()).all()
            
            # Need at least a minimum number of samples for meaningful baseline
            if len(activities) < 5:
                return None
                
            df = self._extract_features(activities)
            features = df[['hour', 'weekday', 'frequency', 'location_code', 'device_code']]
            
            # Fit the model
            self.model.fit(features)
            
            # Predict: 1 for normal, -1 for anomaly
            latest_features = features.tail(1)
            prediction = self.model.predict(latest_features)[0]
            score = self.model.decision_function(latest_features)[0]
            
            if prediction == -1:
                anomaly_score = round(float(abs(score)) * 100, 2)
                risk_level = "High" if anomaly_score > 15 else "Medium"
                
                # Deduplication check: skip if similar alert was recorded within 5 minutes
                five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
                recent_alert = db.query(Alert).filter(
                    Alert.user_id == user_id,
                    Alert.detected_at >= five_mins_ago,
                    Alert.risk_level == risk_level
                ).first()
                if recent_alert:
                    return recent_alert
                
                new_alert = Alert(
                    user_id=user_id,
                    anomaly_score=anomaly_score,
                    risk_level=risk_level,
                    detected_at=datetime.utcnow(),
                    feedback_status="pending",
                    feedback_notes=f"ML Anomaly (Score: {anomaly_score:.1f}): Divergent behavior in timing/frequency/access detected."
                )
                db.add(new_alert)
                db.commit()
                db.refresh(new_alert)
                return new_alert

            return None
        except Exception as e:
            logger.error(f"Anomaly detection error for user {user_id}: {e}")
            return None

