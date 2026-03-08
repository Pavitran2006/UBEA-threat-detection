from fastapi.testclient import TestClient
from app.main import app
import uuid

client = TestClient(app)

def test_flow():
    suffix = str(uuid.uuid4())[:8]
    user = f"user_{suffix}"
    email = f"user_{suffix}@test.com"
    
    print(f"--- Testing Flow for {user} ---")
    # 1. Register
    reg_data = {
        "username": user,
        "email": email,
        "password": "secure123",
        "confirmPassword": "secure123",
        "role": "user"
    }
    resp1 = client.post("/api/register", json=reg_data)
    print("Register:", resp1.status_code, resp1.json())
    
    # 2. Login
    login_data = {"username": user, "password": "secure123"}
    resp2 = client.post("/api/login", json=login_data)
    print("Login:", resp2.status_code, resp2.json())
    
    # Extract access token cookie if exists
    cookies = client.cookies
    print("Cookies after login:", list(cookies.keys()))
    
    # 3. Access Dashboard
    resp3 = client.get("/dashboard", follow_redirects=False)
    print("Dashboard Access Status:", resp3.status_code)
    if resp3.status_code == 200:
        print("Successfully accessed dashboard HTML.")
    else:
        print("Failed to access dashboard.", resp3.headers)
        
    # 4. Logout
    resp4 = client.post("/api/logout")
    print("Logout:", resp4.status_code, resp4.json())
    print("Cookies after logout:", list(client.cookies.keys()))
    
    # 5. Dashboard Access after Logout
    resp5 = client.get("/dashboard", follow_redirects=False)
    print("Dashboard Access after Logout:", resp5.status_code)
    if resp5.status_code == 303:
        print("Successfully redirected to login after logout.")
    else:
        print("Failed redirection behavior.")

if __name__ == "__main__":
    test_flow()
