import sys
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models import User
from app.auth import verify_password, get_password_hash

db = SessionLocal()
users = db.query(User).all()

print("Existing users:")
for u in users:
    pwd_check = verify_password('password123', u.password)
    print(f'  Email: {u.email}, Username: {u.username}, Role: {u.role}, Password OK: {pwd_check}')

# Create admin user if not exists
admin = db.query(User).filter(User.email == 'admin@ueba.local').first()
if not admin:
    print("\nCreating admin user...")
    admin = User(
        username='admin',
        email='admin@ueba.local',
        password=get_password_hash('password123'),
        role='admin',
        risk_score=5.0,
        is_active=True
    )
    db.add(admin)
    db.commit()
    print("Admin user created!")
else:
    print(f"\nAdmin exists: {admin.username}")

db.close()
