from __future__ import annotations

from datetime import datetime, timedelta
import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User, LoginActivity, SecurityAlert, Alert
from ..security import get_current_user
from ..anomaly_engine import compute_anomaly_scores_from_db, compute_risk_score_from_db

router = APIRouter()


@router.get("/api/dashboard/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    total_users = db.query(User).count()
    active_sessions = db.query(LoginActivity).filter(
        LoginActivity.login_time.isnot(None)
    ).count()
    security_alerts = db.query(SecurityAlert).count()
    detected_anomalies = db.query(Alert).filter(Alert.feedback_status == "pending").count()

    return {
        "total_users": total_users,
        "active_sessions": active_sessions,
        "security_alerts": security_alerts,
        "detected_anomalies": detected_anomalies,
    }


@router.get("/api/dashboard/login-map")
async def get_login_map(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    logins = (
        db.query(LoginActivity)
        .order_by(LoginActivity.login_time.desc())
        .limit(100)
        .all()
    )

    result = []
    for login in logins:
        if login.latitude and login.longitude:
            result.append(
                {
                    "username": login.user.username if login.user else "Unknown",
                    "city": login.city or "Unknown",
                    "country": login.country or "Unknown",
                    "latitude": login.latitude,
                    "longitude": login.longitude,
                    "ip_address": login.ip_address or "Unknown",
                    "login_time": login.login_time.isoformat() if login.login_time else None,
                    "risk_score": login.risk_score or 0,
                    "marker_label": f"{login.user.username if login.user else 'User'} - {login.city or ''}, {login.country or ''}",
                }
            )

    return result


@router.get("/api/dashboard/recent-login-activity")
async def get_recent_login_activity(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    activities = (
        db.query(LoginActivity)
        .order_by(LoginActivity.login_time.desc())
        .limit(10)
        .all()
    )

    result = []
    for activity in activities:
        result.append(
            {
                "id": activity.id,
                "username": activity.user.username if activity.user else "Unknown",
                "ip_address": activity.ip_address or "Unknown",
                "city": activity.city or "",
                "country": activity.country or "",
                "browser": activity.browser or "Unknown",
                "device": activity.device or "Unknown",
                "login_time": activity.login_time.isoformat() if activity.login_time else None,
                "risk_score": activity.risk_score or 0,
            }
        )
    return result


@router.get("/api/dashboard/security-alerts")
async def get_security_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    alerts = (
        db.query(SecurityAlert)
        .order_by(SecurityAlert.timestamp.desc())
        .limit(10)
        .all()
    )

    result = []
    for alert in alerts:
        result.append(
            {
                "id": alert.id,
                "alert_type": alert.alert_type or "Unknown",
                "severity": alert.severity or "Low",
                "timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
                "description": alert.description or "",
            }
        )
    return result


@router.get("/api/dashboard/activity")
async def get_activity_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    days = []
    values = []

    for i in range(6, -1, -1):
        date = datetime.utcnow() - timedelta(days=i)
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        day_name = date.strftime("%a")

        count = (
            db.query(LoginActivity)
            .filter(LoginActivity.login_time >= day_start)
            .filter(LoginActivity.login_time < day_end)
            .count()
        )

        days.append(day_name)
        values.append(count)

    return {"labels": days, "values": values}


@router.get("/api/dashboard/risk-distribution")
async def get_risk_distribution(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    low = db.query(User).filter(User.risk_score < 21).count()
    medium = db.query(User).filter(User.risk_score >= 21, User.risk_score < 41).count()
    high = db.query(User).filter(User.risk_score >= 41, User.risk_score < 71).count()
    critical = db.query(User).filter(User.risk_score >= 71).count()

    return {"Low": low, "Medium": medium, "High": high, "Critical": critical}


@router.get("/api/dashboard/alert-severity")
async def get_alert_severity(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    low = db.query(SecurityAlert).filter(SecurityAlert.severity == "Low").count()
    medium = db.query(SecurityAlert).filter(SecurityAlert.severity == "Medium").count()
    high = db.query(SecurityAlert).filter(SecurityAlert.severity == "High").count()
    critical = db.query(SecurityAlert).filter(SecurityAlert.severity == "Critical").count()

    return {"Low": low, "Medium": medium, "High": high, "Critical": critical}


@router.get("/dashboard-data")
async def get_dashboard_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    stats = await get_dashboard_stats(current_user, db)
    activity = await get_activity_data(current_user, db)

    anomalies = {
        "labels": ["T-8", "T-7", "T-6", "T-5", "T-4", "T-3", "T-2", "T-1"],
        "values": [2, 6, 3, 9, 4, 7, 5, 8],
    }

    status = {
        "activeUsers": stats["total_users"],
        "detectedThreats": stats["security_alerts"],
        "normalActivities": stats["active_sessions"],
        "systemHealth": "Healthy" if stats["security_alerts"] < 10 else "Watch",
    }

    return {"status": status, "activity": activity, "anomalies": anomalies}


@router.get("/api/anomalies")
async def get_anomaly_scores(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    results = compute_anomaly_scores_from_db(db)
    if not results:
        return {"labels": [], "values": []}

    values = [int(r["score"]) for r in results[:10]]
    labels = [f"T-{i}" for i in range(len(values), 0, -1)]
    return {"labels": labels, "values": values}


@router.get("/api/risk-score")
async def get_risk_score(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    score, level = compute_risk_score_from_db(db, current_user.id)
    return {"score": score, "level": level}


@router.get("/api/attack-map")
async def get_attack_map(current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    locations = [
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

    attack_types = ["Brute Force", "Malware", "Privilege Escalation", "Data Exfiltration"]
    attacks = []
    for _ in range(10):
        origin = random.choice(locations)
        target = random.choice(locations)
        attacks.append(
            {
                "origin": {"lat": origin["lat"], "lon": origin["lon"], "country": origin["country"]},
                "target": {"lat": target["lat"], "lon": target["lon"], "country": target["country"]},
                "type": random.choice(attack_types),
                "timestamp": datetime.utcnow().strftime("%H:%M:%S UTC"),
            }
        )

    return attacks


@router.get("/api/heatmap")
async def get_heatmap(current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    rows = 6
    cols = 10
    grid = [[random.random() for _ in range(cols)] for _ in range(rows)]
    return {"grid": grid}


@router.get("/api/network-graph")
async def get_network_graph(current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    nodes = []
    for i in range(14):
        nodes.append(
            {
                "id": f"n{i}",
                "type": random.choice(["user", "device", "server"]),
                "x": random.uniform(-25, 25),
                "y": random.uniform(-18, 18),
                "z": random.uniform(-20, 20),
                "suspicious": random.choice([False, False, True]),
            }
        )

    links = []
    for i in range(20):
        source = random.choice(nodes)["id"]
        target = random.choice(nodes)["id"]
        if source != target:
            links.append({"source": source, "target": target})

    return {"nodes": nodes, "links": links}


@router.get("/api/events")
async def get_events(current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    event_types = [
        "Brute Force",
        "Suspicious Login",
        "Privilege Escalation",
        "Data Exfiltration",
        "Malware",
    ]
    messages = [
        "Multiple failed logins detected",
        "Unusual data transfer spike",
        "Privilege escalation attempt blocked",
        "Suspicious IP access pattern",
        "Endpoint malware quarantine triggered",
    ]

    events = []
    for _ in range(10):
        event_type = random.choice(event_types)
        severity = random.choice(["Low", "Medium", "High"])
        events.append(
            {
                "type": event_type,
                "message": random.choice(messages),
                "severity": severity,
                "timestamp": datetime.utcnow().strftime("%H:%M:%S UTC"),
            }
        )

    return {"events": events}


@router.get("/alerts")
async def get_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    alerts = await get_security_alerts(current_user, db)
    formatted = [f"{a['alert_type']} - {a['severity']}" for a in alerts]
    return {"alerts": formatted}
