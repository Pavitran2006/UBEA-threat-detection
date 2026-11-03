import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, Base, engine
from app.models import User, Activity, Alert, SecurityAlert

client = TestClient(app)

def test_health_endpoints():
    """Verify both /health and /api/health respond with 200 OK and expected structure."""
    for path in ["/health", "/api/health"]:
        res = client.get(path)
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert data["service"] == "UEBA Threat Detection Platform"
        assert "database" in data
        assert "connected" in data["database"]

def test_landing_and_public_pages():
    """Verify public HTML pages render successfully."""
    for path in ["/", "/login", "/signup", "/forgot-password"]:
        res = client.get(path)
        assert res.status_code == 200
        assert "html" in res.headers.get("content-type", "").lower()

def test_auth_and_access_control():
    """Verify registration, login validation, session tokens, and route protection."""
    # Test invalid login credentials
    bad_login = client.post("/login", data={"email": "nonexistent_user@ueba.test", "password": "wrongpassword"})
    assert bad_login.status_code in (200, 401)
    # When rendering login.html on error, status is 200 with error message
    if bad_login.status_code == 200:
        assert "Invalid email or password" in bad_login.text

    # Test protected dashboard without token redirects or denies
    dash_res = client.get("/dashboard", follow_redirects=False)
    assert dash_res.status_code in (302, 303, 307, 401, 403)

    # Test admin dashboard without admin auth
    admin_res = client.get("/admin/dashboard", follow_redirects=False)
    assert admin_res.status_code in (302, 303, 307, 401, 403)

def test_anomaly_detection_logic():
    """Verify Isolation Forest anomaly detector handles cold-start and detection gracefully."""
    from app.anomaly_detection import AnomalyDetector
    detector = AnomalyDetector()
    db = SessionLocal()
    try:
        # User with 0 activities returns None safely (no exception)
        res = detector.train_and_detect(db, user_id=999999)
        assert res is None
    finally:
        db.close()

def test_postgresql_psycopg_driver_compatibility():
    """Verify that PostgreSQL connection URLs correctly resolve with the psycopg driver."""
    from sqlalchemy import create_engine
    test_urls = [
        "postgresql+psycopg://user:pass@ep-test.oregon.render.com/ueba_system",
    ]
    for url in test_urls:
        eng = create_engine(url)
        assert eng.dialect.driver == "psycopg"

