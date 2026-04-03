import os
import sys
from datetime import datetime
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Add the project root to sys.path to allow importing from 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.database import SessionLocal, engine
from app.models import User
from app.auth import hash_password

load_dotenv()

def create_test_admin():
    db = SessionLocal()
    try:
        # Check if admin already exists
        admin_email = "admin@ueba.sec"
        existing_admin = db.query(User).filter(User.email == admin_email).first()
        
        if existing_admin:
            print(f"Admin user with email {admin_email} already exists.")
            # Ensure it has the admin role
            if existing_admin.role != "admin":
                existing_admin.role = "admin"
                db.commit()
                print("Updated existing user to admin role.")
            return

        # Create new admin user
        admin_user = User(
            username="SystemAdmin",
            email=admin_email,
            phone="1234567890",
            hashed_password=hash_password("Admin@123"), # Secure default for testing
            role="admin",
            status="active",
            is_active=True,
            is_verified=True,
            created_at=datetime.utcnow()
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        print(f"Successfully created admin user: {admin_email} / Admin@123")
        
    except Exception as e:
        db.rollback()
        print(f"Error creating admin user: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_test_admin()
