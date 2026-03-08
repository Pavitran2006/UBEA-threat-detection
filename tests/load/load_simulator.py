import asyncio
import httpx
import random
import time
import uuid

GATEWAY_URL = "http://localhost:8000"

async def simulate_login(client, user_id):
    correlation_id = str(uuid.uuid4())
    start_time = time.time()
    
    login_data = {
        "email": f"user_{user_id}@example.com",
        "password": "password123", # Mock password
        "tenant_id": "default_tenant"
    }
    
    try:
        response = await client.post(f"{GATEWAY_URL}/api/auth/login", json=login_data, timeout=10.0)
        latency = (time.time() - start_time) * 1000
        print(f"Login User {user_id}: Status {response.status_code}, Risk Score: {response.json().get('risk_score')}, Latency: {latency:.2f}ms")
        return latency
    except Exception as e:
        print(f"Error for user {user_id}: {e}")
        return None

async def run_load_test(num_users=100):
    async with httpx.AsyncClient() as client:
        tasks = [simulate_login(client, i) for i in range(num_users)]
        latencies = await asyncio.gather(*tasks)
        
        valid_latencies = [l for l in latencies if l is not None]
        if valid_latencies:
            p95 = sorted(valid_latencies)[int(len(valid_latencies) * 0.95)]
            avg = sum(valid_latencies) / len(valid_latencies)
            print(f"\nLoad Test Completed: {len(valid_latencies)} successful logins")
            print(f"Average Latency: {avg:.2f}ms")
            print(f"P95 Latency: {p95:.2f}ms")

if __name__ == "__main__":
    print("Starting UEBA Load Simulator...")
    asyncio.run(run_load_test(50)) # Smaller number for quick verification
