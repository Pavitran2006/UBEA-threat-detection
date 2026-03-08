import httpx

def test_redirections():
    base_url = "http://127.0.0.1:8000"
    
    # 1. Test /dashboard without auth
    print("Testing /dashboard redirection...")
    try:
        response = httpx.get(f"{base_url}/dashboard", follow_redirects=False)
        if response.status_code == 303 and response.headers.get("location") == "/login":
            print("SUCCESS: /dashboard redirected to /login")
        else:
            print(f"FAILED: /dashboard returned {response.status_code} and location {response.headers.get('location')}")
    except Exception as e:
        print(f"ERROR: {e}")

    # 2. Test / without auth
    print("\nTesting / redirection...")
    try:
        response = httpx.get(f"{base_url}/", follow_redirects=False)
        if response.status_code == 307 and response.headers.get("location") == "/login":
            print("SUCCESS: / redirected to /login")
        else:
            print(f"FAILED: / returned {response.status_code} and location {response.headers.get('location')}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_redirections()
