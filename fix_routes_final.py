import os

file_path = r"d:\pavi projects\Blockchain and Cybersecurity\UEBA-Project\app\routes.py"

with open(file_path, 'r') as f:
    content = f.read()

# 1. Update recent_login_activity
old_target = """            "city": act.city,
            "country": act.country,
            "risk_score": act.risk_score
        })
    return results"""

new_target = """            "city": act.city,
            "country": act.country,
            "latitude": act.latitude,
            "longitude": act.longitude,
            "risk_score": act.risk_score
        })
    return results"""

if old_target in content:
    content = content.replace(old_target, new_target)
    print("Updated recent_login_activity.")
else:
    print("Could not find recent_login_activity target.")

# 2. Fix corrupted SOC endpoints at the end
# We'll identify the start of the corrupted section
corrupt_start = '@router.get("/api/network-graph")'
if corrupt_start in content:
    parts = content.split(corrupt_start)
    head = parts[0]
    # The rest is likely corrupted or needs replacement
    new_soc_endpoints = """@router.get("/api/network-graph")
async def get_network_graph(db: Session = Depends(get_db)):
    # Simulation of a network graph nodes/links
    return {
        "nodes": [{"id": "Core-Switch", "group": 1}, {"id": "User-Seg-1", "group": 2}, {"id": "DMZ", "group": 3}],
        "links": [{"source": "Core-Switch", "target": "User-Seg-1", "value": 1}, {"source": "Core-Switch", "target": "DMZ", "value": 1}]
    }

@router.get("/api/attack-map")
async def get_attack_map(db: Session = Depends(get_db)):
    # Simulation: Return some recent high-risk logins as attack arcs
    high_risk_activities = db.query(Activity).filter(Activity.risk_score >= 50).order_by(Activity.login_time.desc()).limit(10).all()
    attacks = []
    for act in high_risk_activities:
        attacks.append({
            "origin": {"lat": 20, "lon": 0, "country": "External Actor"}, 
            "target": {"lat": act.latitude, "lon": act.longitude, "country": "Corporate Network"},
            "type": "Suspicious Login",
            "timestamp": act.login_time.isoformat() if act.login_time else datetime.utcnow().isoformat()
        })
    if not attacks:
        attacks = [
            {"origin": {"lat": 55.75, "lon": 37.61, "country": "Russia"}, "target": {"lat": 13.08, "lon": 80.27, "country": "India"}, "type": "Brute Force", "timestamp": datetime.utcnow().isoformat()},
            {"origin": {"lat": 39.90, "lon": 116.40, "country": "China"}, "target": {"lat": 13.08, "lon": 80.27, "country": "India"}, "type": "Malware", "timestamp": datetime.utcnow().isoformat()}
        ]
    return attacks

@router.get("/api/heatmap")
async def get_heatmap(db: Session = Depends(get_db)):
    activities = db.query(Activity).filter(Activity.latitude != None).order_by(Activity.login_time.desc()).limit(100).all()
    return {"grid": [{"lat": a.latitude, "lon": a.longitude, "intensity": (a.risk_score or 10)/100} for a in activities]}

@router.get("/api/events")
async def get_dashboard_events(db: Session = Depends(get_db)):
    activities = db.query(Activity).order_by(Activity.login_time.desc()).limit(10).all()
    events = []
    for act in activities:
        events.append({
            "type": "Login",
            "message": f"User {act.user.username if act.user else 'Unknown'} authenticated from {act.city or 'Unknown'}",
            "timestamp": act.login_time.strftime("%H:%M:%S") if act.login_time else "Now",
            "latitude": act.latitude,
            "longitude": act.longitude,
            "severity": "Low" if (act.risk_score or 0) < 50 else "High"
        })
    return {"events": events}

@router.get("/api/anomalies")
async def get_anomalies(db: Session = Depends(get_db)):
    return {"labels": ["12:00", "13:00"], "values": [10, 20]}

@router.get("/api/risk-score")
async def get_global_risk(db: Session = Depends(get_db)):
    from sqlalchemy import func
    avg_risk = db.query(func.avg(User.risk_score)).scalar() or 0
    level = "Low" if avg_risk < 30 else "Medium" if avg_risk < 70 else "High"
    return {"score": round(avg_risk, 1), "level": level}

@router.get("/dashboard-data")
async def get_combined_dashboard_data(db: Session = Depends(get_db)):
    total_users = db.query(User).count()
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(hours=24)
    active_users = db.query(Activity.user_id).filter(
        Activity.login_time >= since,
        Activity.status == 'success'
    ).distinct().count()
    security_alerts = db.query(SecurityAlert).count()
    return {
        "status": {
            "activeUsers": active_users,
            "detectedThreats": security_alerts,
            "normalActivities": total_users,
            "systemHealth": "Healthy"
        }
    }

@router.get("/alerts")
async def get_simple_alerts(db: Session = Depends(get_db)):
    alerts = db.query(SecurityAlert).order_by(SecurityAlert.timestamp.desc()).limit(10).all()
    return {"alerts": [a.description for a in alerts]}

@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket, token: str = None):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        manager.disconnect(websocket)
"""
    content = head + new_soc_endpoints
    print("Fixed corrupted SOC segment.")
else:
    print("Could not find start of corrupted segment.")

with open(file_path, 'w') as f:
    f.write(content)

print("File update complete.")
