import pandas as pd
from sklearn.ensemble import IsolationForest
from sqlalchemy.orm import Session
from app.models import Activity, Alert, User
from datetime import datetime

class AnomalyDetector:
    def __init__(self):
        # We use an IsolationForest to detect structural outliers in login behavior
        self.model = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
        
    def _extract_features(self, activities):
        """Convert a list of models.Activity into a pandas DataFrame suitable for IsolationForest."""
        data = []
        for i, act in enumerate(activities):
            hour = act.login_time.hour
            weekday = act.login_time.weekday()
            
            # Frequency: time since last login in hours
            if i > 0:
                time_diff = (activities[i].login_time - activities[i-1].login_time).total_seconds() / 3600.0
            else:
                time_diff = 0.0 # Or some median value
            
            # Use stable hashing for categorical features
            import hashlib
            def stable_hash(s):
                return int(hashlib.md5(str(s).encode()).hexdigest(), 16) % 1000
                
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
        # Fetch user's history
        activities = db.query(Activity).filter(Activity.user_id == user_id).order_by(Activity.login_time.asc()).all()
        
        # Need at least a minimum number of samples
        if len(activities) < 10:
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
            # We detected a structural anomaly
            anomaly_score = float(abs(score)) * 100
            
            # Generate Alert
            risk_level = "High" if anomaly_score > 15 else "Medium"
            
            new_alert = Alert(
                user_id=user_id,
                anomaly_score=anomaly_score,
                risk_level=risk_level,
                detected_at=datetime.utcnow(),
                feedback_notes=f"ML Anomaly (Score: {anomaly_score:.1f}): Divergent behavior in timing/frequency/access detected."
            )
            db.add(new_alert)
            db.commit()
            return new_alert

        return None
