import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app.models import User

db = SessionLocal()
try:
    users = db.query(User).all()
    print("Users in DB:")
    for u in users:
        print(f"Email: {u.email}, Role: {u.role}, Active: {u.is_active}")
except Exception as e:
    print(f"Error: {str(e)}")
finally:
    db.close()
