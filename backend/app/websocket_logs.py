from __future__ import annotations

import asyncio
import random
from datetime import datetime

from fastapi import WebSocket

from .auth import decode_access_token
from .database import SessionLocal
from .models.user import User

EVENT_TYPES = [
    "Brute Force",
    "Privilege Escalation",
    "Data Exfiltration",
    "Malware",
    "Suspicious Login",
    "Failed Login",
]

MESSAGES = [
    "Multiple failed logins detected",
    "Unusual data transfer spike",
    "Privilege escalation attempt blocked",
    "Malware signature detected on endpoint",
    "Suspicious IP access pattern",
    "Credential stuffing attempt flagged",
]

SEVERITIES = ["Low", "Medium", "High"]

LOCATIONS = [
    {"lat": 37.7749, "lon": -122.4194, "country": "United States"},
    {"lat": 40.7128, "lon": -74.0060, "country": "United States"},
    {"lat": 51.5074, "lon": -0.1278, "country": "United Kingdom"},
    {"lat": 35.6895, "lon": 139.6917, "country": "Japan"},
    {"lat": 1.3521, "lon": 103.8198, "country": "Singapore"},
    {"lat": -33.8688, "lon": 151.2093, "country": "Australia"},
    {"lat": 55.7558, "lon": 37.6173, "country": "Russia"},
    {"lat": 19.0760, "lon": 72.8777, "country": "India"},
    {"lat": 48.8566, "lon": 2.3522, "country": "France"},
    {"lat": -23.5505, "lon": -46.6333, "country": "Brazil"},
]


async def events_websocket(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        await websocket.close(code=1008)
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == payload.get("sub")).first()
        if not user:
            await websocket.close(code=1008)
            return

        await websocket.accept()

        while True:
            event_type = random.choice(EVENT_TYPES)
            message = random.choice(MESSAGES)
            severity = random.choice(SEVERITIES)
            origin = random.choice(LOCATIONS)
            target = random.choice(LOCATIONS)
            await websocket.send_json(
                {
                    "type": event_type,
                    "message": message,
                    "severity": severity,
                    "timestamp": datetime.utcnow().strftime("%H:%M:%S UTC"),
                    "origin": {
                        "lat": origin["lat"],
                        "lon": origin["lon"],
                        "country": origin["country"],
                    },
                    "target": {
                        "lat": target["lat"],
                        "lon": target["lon"],
                        "country": target["country"],
                    },
                }
            )
            await asyncio.sleep(random.uniform(1.0, 2.5))
    finally:
        db.close()
