import pandas as pd
import numpy as np
import joblib
import os
from sklearn.ensemble import IsolationForest
from app.models import Activity, Alert
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
MODEL_PATH = 'ml_models/ueba_isolation_forest.joblib'

class MLService:
    @staticmethod
    def extract_features(db, user_id):
        """
        Extracts advanced features for a user:
        - Login hour
        - Login velocity (hours since last login)
        - IP change flag
        - Failed attempts count (last 24h)
        - Device fingerprint change flag
        """
        activities = db.query(Activity).filter_by(user_id=user_id).order_by(Activity.login_time.desc()).limit(100).all()
        
        if len(activities) < 2:
            return None
            
        latest = activities[0]
        prev = activities[1]
        
        # 1. Login Hour
        hour = latest.login_time.hour
        
        # 2. Login Velocity (in hours)
        time_diff = (latest.login_time - prev.login_time).total_seconds() / 3600.0
        velocity = min(time_diff, 24.0) # Cap at 24h
        
        # 3. IP Change
        ip_change = 1 if latest.ip_address != prev.ip_address else 0

        # 4. Location Change
        loc_change = 1 if latest.location != prev.location else 0
        
        # 5. Failed Attempts (last 24h)
        last_24h = datetime.utcnow() - timedelta(hours=24)
        failed_count = db.query(Activity).filter(
            Activity.user_id == user_id,
            Activity.status == 'failed',
            Activity.login_time >= last_24h
        ).count()
        
        # 6. Device Fingerprint Change
        fp_change = 1 if latest.device_fingerprint != prev.device_fingerprint else 0
        
        return [hour, velocity, ip_change, loc_change, failed_count, fp_change]

    @staticmethod
    def train_model(db):
        """
        Trains or retrains the model using historical data and confirmed alerts.
        """
        try:
            # Fetch all successful activities as training baseline
            activities = db.query(Activity).filter_by(status='success').all()
            
            data = []
            for i in range(1, len(activities)):
                user_id = activities[i].user_id
                # This is a simplified training loop for demo purposes
                # In production, we'd pre-calculate a feature matrix
                hour = activities[i].login_time.hour
                time_diff = (activities[i].login_time - activities[i-1].login_time).total_seconds() / 3600.0 if activities[i].user_id == activities[i-1].user_id else 24.0
                ip_change = 1 if activities[i].ip_address != activities[i-1].ip_address else 0
                loc_change = 1 if activities[i].location != activities[i-1].location else 0
                
                data.append([hour, min(time_diff, 24.0), ip_change, loc_change, 0, 0])

            if len(data) < 10:
                logger.warning("Insufficient data for model training")
                return False

            # Optimized Hyperparameters
            model = IsolationForest(
                n_estimators=200, 
                contamination=0.05,
                max_samples='auto',
                random_state=42
            )
            
            df = pd.DataFrame(data)
            model.fit(df)
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(MODEL_PATH) or '.', exist_ok=True)
            
            # Save model
            joblib.dump(model, MODEL_PATH)
            logger.info("ML Model retrained and saved successfully.")
            return True
        except Exception as e:
            logger.error(f"Model training error: {str(e)}")
            return False

    @staticmethod
    def predict_anomaly(db, user_id):
        """
        Predicts if the latest activity is anomalous using the trained model.
        """
        try:
            features = MLService.extract_features(db, user_id)
            if not features:
                return None
                
            if not os.path.exists(MODEL_PATH):
                # Fallback to initial training if model missing
                MLService.train_model(db)
                
            if not os.path.exists(MODEL_PATH):
                logger.warning("Model file not found and training failed")
                return None
                
            model = joblib.load(MODEL_PATH)
            feature_arr = np.array([features])
            prediction = model.predict(feature_arr)
            score = float(model.decision_function(feature_arr)[0])
            
            return prediction[0], score # -1 for anomaly
        except Exception as e:
            logger.error(f"Prediction Error: {e}")
            return None

    @staticmethod
    def scan_all_users(db):
        """Run anomaly prediction for every user in the database and create alerts."""
        from app.models import User, AnomalyAlert
        users = db.query(User).all()
        anomalies = []
        for u in users:
            res = MLService.predict_anomaly(db, u.id)
            if res and res[0] == -1:
                score = res[1]
                if score < -0.5:
                    risk = "High"
                elif score < -0.2:
                    risk = "Medium"
                else:
                    risk = "Low"
                # mark user suspicious
                u.risk_score = max(u.risk_score or 0.0, abs(score) * 100)
                if risk in ["High", "Medium"]:
                    u.is_suspicious = True

                # grab latest activity to annotate the alert with an IP address
                latest_act = db.query(Activity).filter_by(user_id=u.id).order_by(Activity.login_time.desc()).first()
                ip_addr = latest_act.ip_address if latest_act and latest_act.ip_address else None

                # create the public alert record
                alert = Alert(user_id=u.id, anomaly_score=score, risk_level=risk, ip_address=ip_addr)
                db.add(alert)

                # also store in the auxiliary AnomalyAlert table
                try:
                    anomaly_rec = AnomalyAlert(user_id=u.id, anomaly_score=score, risk_level=risk)
                    db.add(anomaly_rec)
                except Exception:
                    pass

                anomalies.append((u.username, score, risk))
        db.commit()
        return anomalies
