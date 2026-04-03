import asyncio
import random
import json
from datetime import datetime
from app.websocket_manager import manager
from app.database import SessionLocal
from sqlalchemy import func
from app.models import User, Activity, SecurityAlert

class SimulationService:
    def __init__(self):
        self.running = False

    async def start(self):
        self.running = True
        print("Simulation Service Started (Lively Tracking)")
        while self.running:
            try:
                await self.generate_mock_event()
                # Wait between 3 to 8 seconds for a more lively experience
                await asyncio.sleep(random.uniform(3, 8))
            except Exception as e:
                print(f"Simulation Error: {str(e)}")
                await asyncio.sleep(10)

    async def generate_mock_event(self):
        event_type = random.choice(['login', 'alert', 'location_update'])
        
        db = SessionLocal()
        try:
            # Pick a random user for the event (MySQL RAND())
            user = db.query(User).order_by(func.rand()).first()
            if not user:
                return

            if event_type == 'login':
                regions = [
                    {"city": "San Francisco", "country": "USA", "lat": 37.7749, "lon": -122.4194},
                    {"city": "London", "country": "UK", "lat": 51.5074, "lon": -0.1278},
                    {"city": "Tokyo", "country": "Japan", "lat": 35.6895, "lon": 139.6917},
                    {"city": "Berlin", "country": "Germany", "lat": 52.5200, "lon": 13.4050},
                    {"city": "Mumbai", "country": "India", "lat": 19.0760, "lon": 72.8777},
                    {"city": "Sydney", "country": "Australia", "lat": -33.8688, "lon": 151.2093},
                    {"city": "Dubai", "country": "UAE", "lat": 25.2048, "lon": 55.2708},
                    {"city": "Paris", "country": "France", "lat": 48.8566, "lon": 2.3522}
                ]
                loc = random.choice(regions)
                risk_score = random.uniform(0, 100)
                is_threat = risk_score >= 80
                
                payload = {
                    "type": "login",
                    "username": user.username,
                    "ip_address": f"{random.randint(1, 230)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
                    "city": loc["city"],
                    "country": loc["country"],
                    "lat": loc["lat"],
                    "lon": loc["lon"],
                    "latitude": loc["lat"],
                    "longitude": loc["lon"],
                    "risk_score": round(risk_score, 1),
                    "is_threat": is_threat,
                    "status": "success"
                }
                await manager.broadcast(payload)

            elif event_type == 'alert':
                # Simulate a security alert
                alert_types = ["Brute Force Attempt", "Impossible Travel", "Malicious Link Clicked", "Credential Stuffing"]
                payload = {
                    "type": "alert",
                    "alert_type": random.choice(alert_types),
                    "severity": random.choice(["Medium", "High", "Critical"]),
                    "description": f"Heuristic detection triggered for {user.username}",
                    "ip_address": f"45.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"
                }
                await manager.broadcast(payload)

            elif event_type == 'location_update':
                # Simulate a moving user (Live tracking)
                # If the user has a recent activity, move from there
                act = db.query(Activity).filter(Activity.user_id == user.id).order_by(Activity.login_time.desc()).first()
                base_lat = act.latitude if (act and act.latitude) else 13.08
                base_lon = act.longitude if (act and act.longitude) else 80.27
                
                new_lat = base_lat + random.uniform(-0.01, 0.01)
                new_lon = base_lon + random.uniform(-0.01, 0.01)
                
                payload = {
                    "type": "location_update",
                    "user_id": user.id,
                    "username": user.username,
                    "latitude": new_lat,
                    "longitude": new_lon,
                    "risk_score": user.risk_score or 10,
                    "timestamp": datetime.utcnow().isoformat()
                }
                await manager.broadcast(payload)
                
        finally:
            db.close()

simulator = SimulationService()
