from app import app, db
from models.user import User
from models.activity import Activity
from models.alert import Alert
from services.ml_service import MLService
from datetime import datetime
import json

def test_feedback_loop():
    with app.app_context():
        # 1. Ensure a model is trained
        print("Training initial model...")
        MLService.train_model()
        
        # 2. Find an alert to give feedback on
        alert = Alert.query.order_by(Alert.detected_at.desc()).first()
        if not alert:
            print("No alerts found to test feedback. Creating a mock alert...")
            user = User.query.first()
            alert = Alert(user_id=user.id, anomaly_score=0.9, risk_level='High')
            db.session.add(alert)
            db.session.commit()
            
        print(f"Submitting feedback for Alert ID: {alert.id}")
        
        # 3. Simulate Admin Feedback via Test Client
        with app.test_client() as client:
            response = client.post('/api/ml/feedback', 
                data=json.dumps({
                    "alert_id": alert.id,
                    "status": "confirmed",
                    "notes": "Verified suspicious login from anomalous VPN IP."
                }),
                content_type='application/json'
            )
            
            if response.status_code == 200:
                print("Feedback SUCCESS: " + response.get_json().get('message'))
            else:
                print(f"Feedback FAILURE: {response.status_code} - {response.get_data(as_text=True)}")

        # 4. Verify DB status
        db.session.refresh(alert)
        print(f"Updated Alert Status: {alert.feedback_status}")
        
        if alert.feedback_status == 'confirmed':
            print("VERIFICATION COMPLETE: Feedback loop operational.")

if __name__ == '__main__':
    test_feedback_loop()
