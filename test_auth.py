import httpx
import asyncio

async def test_auth_flow():
    print("--- Testing Auth Flow Locally ---")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8050") as client:
        # Test Registration
        register_payload = {
            "username": "testoperator",
            "email": "operator@test.com",
            "password": "securepassword123",
            "confirmPassword": "securepassword123",
            "role": "admin"
        }
        r_resp = await client.post("/api/register", json=register_payload)
        print(f"Register Status: {r_resp.status_code}")
        print(f"Register Body: {r_resp.json()}")

        # Test Login
        login_payload = {
            "username": "testoperator",
            "password": "securepassword123"
        }
        l_resp = await client.post("/api/login", json=login_payload)
        print(f"Login Status: {l_resp.status_code}")
        print(f"Login Headers (Set-Cookie): {l_resp.headers.get('set-cookie')}")

        # Test Protected Dashboard
        d_resp = await client.get("/dashboard", follow_redirects=False)
        print(f"Dashboard Access Status: {d_resp.status_code}")

if __name__ == "__main__":
    asyncio.run(test_auth_flow())
