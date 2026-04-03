import requests
from app.database import SessionLocal
from app.models import User

def get_test_creds():
    db = SessionLocal()
    user = db.query(User).first()
    db.close()
    if user:
        return user.email, "admin123" # usually we use a known password or we can just force update it
    return None, None

def test_login():
    email, _ = get_test_creds()
    if not email:
        print("No user found")
        return
        
    print(f"Testing with email: {email}")
    url = "http://127.0.0.1:8000/login"
    
    # Let's force update password so we know it works
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    from app.auth import hash_password
    user.hashed_password = hash_password("Admin@123")
    db.commit()
    db.close()
    
    data = {
        "email": email, 
        "password": "Admin@123"
    }
    headers = {
        "X-Requested-With": "XMLHttpRequest"
    }
    try:
        response = requests.post(url, data=data, headers=headers)
        print("Status Code:", response.status_code)
        print("Response Headers:", response.headers)
        print("Response Text:", response.text)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_login()
