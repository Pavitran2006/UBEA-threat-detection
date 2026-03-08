import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from app.models import Activity, Alert
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AnomalyService:
    @staticmethod
    def detect_anomaly(db, user_id):
        """
        Extracts features for a user, runs Isolation Forest, 
        and generates an alert if behavior is suspicious.
        """
        try:
            # 1. Fetch activities for the user
            activities = db.query(Activity).filter_by(user_id=user_id).order_by(Activity.login_time.desc()).limit(50).all()
            
            if len(activities) < 5:
                # Need at least 5 logins to build a baseline
                return None

            # 2. Extract Features
            data = []
            for act in activities:
                # Login hour (0-23)
                hour = act.login_time.hour
                
                # Check for IP change (simplified: just use the IP string)
                # In a real app, we'd compare with the previous IP
                ip_val = hash(act.ip_address) % 1000
                
                data.append([hour, ip_val])

            df = pd.DataFrame(data, columns=['hour', 'ip_val'])

            # 3. Train/Predict with Isolation Forest
            # contamination is the expected proportion of outliers (set to 10%)
            model = IsolationForest(contamination=0.1, random_state=42)
            model.fit(df)
            
            # Predict the latest login (the first in our list)
            latest_features = np.array([[activities[0].login_time.hour, hash(activities[0].ip_address) % 1000]])
            prediction = model.predict(latest_features) # -1 for anomaly, 1 for normal
            
            # Get anomaly score (lower is more anomalous)
            score = float(model.decision_function(latest_features)[0])

            # 4. If Anomaly detected (-1), create alert
            if prediction[0] == -1:
                risk_level = "Low"
                if score < -0.1: risk_level = "High"
                elif score < -0.05: risk_level = "Medium"

                # capture the IP from the most recent activity so the alert can be
                # correlated in the UI panel.  the activities list is ordered
                # descending so index 0 is the latest entry.
                ip_addr = activities[0].ip_address if activities and activities[0].ip_address else None

                # create a user-facing alert record
                new_alert = Alert(
                    user_id=user_id,
                    anomaly_score=abs(score),
                    risk_level=risk_level,
                    detected_at=datetime.utcnow(),
                    tenant_id='default',
                    ip_address=ip_addr,
                )
                db.add(new_alert)

                # mirror into the simpler AnomalyAlert table as well (used by the
                # admin /api/anomalies endpoint) so the two dashboards stay in sync
                try:
                    from app.models import AnomalyAlert
                    anomaly_rec = AnomalyAlert(
                        user_id=user_id,
                        anomaly_score=score,
                        risk_level=risk_level,
                    )
                    db.add(anomaly_rec)
                except Exception:
                    # if the secondary table isn't available don't fail detection
                    pass

                db.commit()
                
                logger.warning(f"Anomaly detected for user {user_id}! Risk: {risk_level}, Score: {score}")
                return risk_level
            
            return None

        except Exception as e:
            logger.error(f"Error in Anomaly Detection: {str(e)}")
            return None
