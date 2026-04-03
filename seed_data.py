#!/usr/bin/env python3
"""
Seed script to populate the UEBA database with sample data.
Run this script to populate the dashboard with sample users, login activities, and alerts.
"""

import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine, Base
from app.models import User, LoginActivity, SecurityAlert, Alert
from app.auth import get_password_hash
from datetime import datetime, timedelta
import random

# Sample data
SAMPLE_USERS = [
    {"username": "admin", "email": "admin@ueba.local", "role": "admin", "risk_score": 5.0},
    {"username": "john_doe", "email": "john@example.com", "role": "user", "risk_score": 15.0},
    {"username": "jane_smith", "email": "jane@example.com", "role": "user", "risk_score": 22.0},
    {"username": "bob_wilson", "email": "bob@example.com", "role": "user", "risk_score": 35.0},
    {"username": "alice_jones", "email": "alice@example.com", "role": "user", "risk_score": 48.0},
    {"username": "charlie_brown", "email": "charlie@example.com", "role": "user", "risk_score": 65.0},
    {"username": "david_lee", "email": "david@example.com", "role": "user", "risk_score": 78.0},
    {"username": "emma_davis", "email": "emma@example.com", "role": "user", "risk_score": 12.0},
    {"username": "frank_miller", "email": "frank@example.com", "role": "user", "risk_score": 28.0},
    {"username": "grace_taylor", "email": "grace@example.com", "role": "user", "risk_score": 42.0},
]

SAMPLE_LOCATIONS = [
    {"city": "New York", "country": "USA", "lat": 40.7128, "lng": -74.0060},
    {"city": "London", "country": "UK", "lat": 51.5074, "lng": -0.1278},
    {"city": "Tokyo", "country": "Japan", "lat": 35.6762, "lng": 139.6503},
    {"city": "Sydney", "country": "Australia", "lat": -33.8688, "lng": 151.2093},
    {"city": "Berlin", "country": "Germany", "lat": 52.5200, "lng": 13.4050},
    {"city": "Paris", "country": "France", "lat": 48.8566, "lng": 2.3522},
    {"city": "Mumbai", "country": "India", "lat": 19.0760, "lng": 72.8777},
    {"city": "Toronto", "country": "Canada", "lat": 43.6532, "lng": -79.3832},
    {"city": "Singapore", "country": "Singapore", "lat": 1.3521, "lng": 103.8198},
    {"city": "Dubai", "country": "UAE", "lat": 25.2048, "lng": 55.2708},
]

BROWSERS = ["Chrome", "Firefox", "Safari", "Edge", "Opera"]
DEVICES = ["Windows PC", "MacBook", "iPhone 14", "Android Phone", "Linux Desktop", "iPad Pro"]

ALERT_TYPES = [
    ("Unusual Login Location", "Medium"),
    ("Multiple Failed Login Attempts", "High"),
    ("New Device Detected", "Low"),
    ("Suspicious IP Address", "High"),
    ("Account Risk Score Increased", "Medium"),
    ("Brute Force Attempt Detected", "Critical"),
    ("Geolocation Anomaly", "Medium"),
    ("Impossible Travel Detected", "Critical"),
]


def seed_database():
    """Seed the database with sample data."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Check if data already exists
        existing_users = db.query(User).count()
        if existing_users > 0:
            print(f"Database already has {existing_users} users. Adding additional data...")
        
        # Create or get users
        users = db.query(User).all()
        if len(users) == 0:
            print("Seeding users...")
            for user_data in SAMPLE_USERS:
                user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    password=get_password_hash("password123"),
                    role=user_data["role"],
                    risk_score=user_data["risk_score"],
                    is_active=True
                )
                db.add(user)
                users.append(user)
            
            db.commit()
            
            # Refresh to get IDs
            for user in users:
                db.refresh(user)
            
            print(f"Created {len(users)} users")
        else:
            print(f"Using {len(users)} existing users")
        
        print("Seeding login activities...")
        # Create login activities for each user
        login_count = 0
        for user in users:
            # Create 5-15 login activities per user
            num_logins = random.randint(5, 15)
            for _ in range(num_logins):
                location = random.choice(SAMPLE_LOCATIONS)
                login_time = datetime.now() - timedelta(
                    days=random.randint(0, 30),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59)
                )
                
                login = LoginActivity(
                    user_id=user.id,
                    ip_address=f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
                    country=location["country"],
                    city=location["city"],
                    latitude=location["lat"] + random.uniform(-0.5, 0.5),
                    longitude=location["lng"] + random.uniform(-0.5, 0.5),
                    device=random.choice(DEVICES),
                    browser=random.choice(BROWSERS),
                    login_time=login_time,
                    risk_score=random.uniform(0, 100)
                )
                db.add(login)
                login_count += 1
        
        db.commit()
        print(f"Created {login_count} login activities")
        
        print("Seeding security alerts...")
        # Create security alerts
        alert_count = 0
        for _ in range(20):
            user = random.choice(users)
            alert_type, severity = random.choice(ALERT_TYPES)
            
            alert = SecurityAlert(
                user_id=user.id,
                alert_type=alert_type,
                description=f"Security alert for user {user.username}: {alert_type} detected from IP address",
                severity=severity,
                timestamp=datetime.now() - timedelta(
                    days=random.randint(0, 14),
                    hours=random.randint(0, 23)
                )
            )
            db.add(alert)
            alert_count += 1
        
        db.commit()
        print(f"Created {alert_count} security alerts")
        
        print("Seeding anomaly alerts...")
        # Create anomaly alerts
        anomaly_count = 0
        for _ in range(15):
            user = random.choice(users)
            
            alert = Alert(
                user_id=user.id,
                anomaly_score=random.uniform(0.5, 1.0),
                risk_level=random.choice(["Low", "Medium", "High", "Critical"]),
                detected_at=datetime.now() - timedelta(days=random.randint(0, 7)),
                ip_address=f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
                feedback_status=random.choice(["pending", "safe", "threat"])
            )
            db.add(alert)
            anomaly_count += 1
        
        db.commit()
        print(f"Created {anomaly_count} anomaly alerts")
        
        print("\n✅ Database seeded successfully!")
        print("\nTest credentials:")
        print("  Email: admin@ueba.local  |  Password: password123  (Admin)")
        print("  Email: john@example.com |  Password: password123  (User)")
        
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()

