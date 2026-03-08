from app.database import SessionLocal, engine
from app.models import Base, User, Activity, Alert
from app.auth import get_password_hash
from datetime import datetime, timedelta

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Check if admin exists
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(
            username="admin",
            email="admin@cyberguard.sec",
            hashed_password=get_password_hash("password123"),
            role="admin",
            risk_score=45.5
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print("Admin user created: admin / password123")

    # Add some activities
    if db.query(Activity).count() == 0:
        activities = [
            Activity(user_id=admin.id, ip_address="192.168.1.10", device_info="Chrome/Windows", status="success"),
            Activity(user_id=admin.id, ip_address="10.0.0.5", device_info="Firefox/Linux", status="success"),
            Activity(user_id=admin.id, ip_address="172.16.0.2", device_info="Safari/MacOS", status="failed")
        ]
        db.add_all(activities)
        print("Activities seeded.")

    # Add some alerts
    if db.query(Alert).count() == 0:
        alerts = [
            Alert(user_id=admin.id, anomaly_score=0.89, risk_level="High", ip_address="203.0.113.5", feedback_status="pending"),
            Alert(user_id=admin.id, anomaly_score=0.45, risk_level="Medium", ip_address="198.51.100.22", feedback_status="confirmed"),
            Alert(user_id=admin.id, anomaly_score=0.98, risk_level="Critical", ip_address="192.0.2.8", feedback_status="pending")
        ]
        db.add_all(alerts)
        print("Alerts seeded.")

    db.commit()
    db.close()

if __name__ == "__main__":
    seed()
