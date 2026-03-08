import httpx
import asyncio

async def verify_endpoints():
    print("--- Verifying Local Endpoints ---")
    async with httpx.AsyncClient() as client:
        # Check Stats
        try:
            stats_resp = await client.get("http://127.0.0.1:5000/api/dashboard/stats")
            print(f"Stats Endpoint: {stats_resp.status_code}")
            print(stats_resp.json())
        except Exception as e:
            print(f"Stats Error: {e}")
            
        # Check Alerts
        try:
            alerts_resp = await client.get("http://127.0.0.1:5000/api/dashboard/alerts")
            print(f"Alerts Endpoint: {alerts_resp.status_code}")
            print(alerts_resp.json())
        except Exception as e:
            print(f"Alerts Error: {e}")

if __name__ == "__main__":
    asyncio.run(verify_endpoints())
