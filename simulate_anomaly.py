from app import app, db
from models.user import User
from models.activity import Activity
from models.alert import Alert
from services.anomaly_service import AnomalyService
from datetime import datetime, timedelta
import random

def simulate_behavior():
    with app.app_context():
        # Get or create test user
        user = User.query.filter_by(username='test_user').first()
        if not user:
            user = User(username='test_user', email='test@ueba.sec', role='user')
            user.password = 'dummy'
            db.session.add(user)
            db.session.commit()
            print("Test user created.")

        # 1. Simulate NORMAL behavior (10 logins at 9 AM)
        print("Simulating normal behavior (10 logins at 9 AM)...")
        base_time = datetime.utcnow() - timedelta(days=2)
        for i in range(10):
            login_time = base_time.replace(hour=9, minute=0) + timedelta(minutes=i*10)
            act = Activity(user_id=user.id, login_time=login_time, ip_address='192.168.1.10', device_info='Workstation')
            db.session.add(act)
        db.session.commit()

        # 2. Simulate ANOMALOUS behavior (1 login at 3 AM from different IP)
        print("Simulating anomalous behavior (3 AM login, different IP)...")
        anomalous_time = datetime.utcnow().replace(hour=3, minute=0)
        act_anomaly = Activity(user_id=user.id, login_time=anomalous_time, ip_address='203.0.113.5', device_info='UnknownDevice')
        db.session.add(act_anomaly)
        db.session.commit()

        # 3. Trigger Detection
        print("Triggering anomaly detection...")
        result = AnomalyService.detect_anomaly(user.id)
        
        if result:
            print(f"SUCCESS: Anomaly detected! Risk Level: {result}")
            # Check Alerts table
            latest_alert = Alert.query.filter_by(user_id=user.id).order_by(Alert.detected_at.desc()).first()
            if latest_alert:
                print(f"Alert recorded: Risk={latest_alert.risk_level}, Score={latest_alert.anomaly_score}")
        else:
            print("FAILURE: No anomaly detected.")

if __name__ == '__main__':
    simulate_behavior()
