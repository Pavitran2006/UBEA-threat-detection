import httpx
import sys

def verify_login():
    url = "http://127.0.0.1:8000/login"
    
    # Test 1: Invalid login
    print("Testing invalid login...")
    data = {"email": "nonexistent@test.com", "password": "wrongpassword"}
    with httpx.Client() as client:
        try:
            response = client.post(url, data=data, follow_redirects=False)
            print(f"Status: {response.status_code}")
            if response.status_code == 302 and "/login?error=" in response.headers.get("Location", ""):
                print("PASSED: Redirected back to login with error.")
            else:
                print(f"FAILED: Expected 302 to /login with error, got {response.status_code} to {response.headers.get('Location')}")
        except Exception as e:
            print(f"ERROR: {e}")

    # Test 2: Correct login (admin)
    print("\nTesting correct login...")
    data = {"email": "admin@cyberguard.sec", "password": "password123"}
    with httpx.Client() as client:
        try:
            response = client.post(url, data=data, follow_redirects=False)
            print(f"Status: {response.status_code}")
            if response.status_code == 302 and "/dashboard" in response.headers.get("Location", ""):
                print("PASSED: Redirected to dashboard.")
                if "access_token" in response.cookies:
                    print("PASSED: Access token cookie set.")
                else:
                    print("FAILED: Access token cookie NOT set.")
            else:
                print(f"FAILED: Expected 302 to /dashboard, got {response.status_code} to {response.headers.get('Location')}")
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    verify_login()
