import requests
import json
import time
import random

GATEWAY_URL = "http://localhost:8000/api/dashboard/stats"
INGESTION_URL = "http://localhost:8001/ingest/login"

def simulate_stream():
    users = [
        {"user_id": 1, "username": "admin"},
        {"user_id": 2, "username": "pavit"},
        {"user_id": 3, "username": "threat_actor"}
    ]
    
    ips = ["192.168.1.1", "10.0.0.5", "172.16.0.100", "45.33.22.11"]
    
    print("Starting UEBA Stream Simulation...")
    
    for i in range(50):
        user = random.choice(users)
        ip = random.choice(ips)
        
        # Simulate a normal login or an anomaly
        status = "success"
        if user['username'] == 'threat_actor' and random.random() > 0.5:
            # Simulate anomaly by changing IP rapidly or unusual device
            ip = "unknown_vpn_ip_" + str(random.randint(1, 100))
        
        payload = {
            "user_id": user['user_id'],
            "username": user['username'],
            "ip_address": ip,
            "device_info": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "status": status
        }
        
        try:
            # Send to INGESTION service (running on 8001 in docker)
            # If running locally for testing, adjust ports
            response = requests.post(f"http://localhost:8001/ingest/login", json=payload)
            print(f"[{i}] Ingested event for {user['username']} - Status: {response.status_code}")
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(random.uniform(0.5, 2.0))

if __name__ == "__main__":
    simulate_stream()
