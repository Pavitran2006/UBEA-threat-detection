from app import app, db
from models.user import User
from models.activity import Activity
from models.alert import Alert
import datetime

def seed_data():
    with app.app_context():
        # Force fresh schema for ML features
        print("Re-initializing database schema...")
        db.drop_all()
        db.create_all()
        
        # Create a sample user
        if User.query.filter_by(username='admin').first() is None:
            admin = User(username='admin', email='admin@ueba.sec', role='admin')
            admin.password = '$2b$12$LQv3c1VqBWVH6N3H1R.3.O6qQ6W6Q6W6Q6W6Q6W6Q6W6Q6W6Q6W6' # 'password' hashed
            db.session.add(admin)
            db.session.commit()
            print("Admin user created.")

            # Create some activities with status and fingerprints
            activity1 = Activity(
                user_id=admin.id, 
                ip_address='192.168.1.1', 
                device_info='Chrome / Windows',
                status='success',
                device_fingerprint='fp_admin_1'
            )
            activity2 = Activity(
                user_id=admin.id, 
                ip_address='10.0.0.5', 
                device_info='Python-Requests',
                status='success',
                device_fingerprint='fp_admin_2'
            )
            db.session.add(activity1)
            db.session.add(activity2)
            
            # Create an alert
            alert = Alert(
                user_id=admin.id, 
                anomaly_score=0.85, 
                risk_level='High',
                feedback_status='pending'
            )
            db.session.add(alert)
            
            db.session.commit()
            print("Sample activities and alerts seeded with new schema.")
        else:
            print("Data already seeded.")

if __name__ == '__main__':
    seed_data()
