from typing import Optional, Any
from urllib.parse import urlencode
import os
import logging
import ipaddress
from datetime import datetime, timedelta
from datetime import timezone
from uuid import uuid4

import httpx
import numpy as np
from fastapi import Depends, FastAPI, Form, HTTPException, Request, status, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from sklearn.ensemble import IsolationForest
from sqlalchemy import func, or_, inspect, text
from sqlalchemy.orm import Session

# OAuth support
try:
    from authlib.integrations.starlette_client import OAuth, OAuthError
except ImportError:
    OAuth = None
    OAuthError = Exception
    logger = logging.getLogger(__name__)
    logger.warning("authlib not installed; OAuth routes will be disabled")
from dotenv import load_dotenv

load_dotenv()

# configure basic logging so that errors show up in the terminal
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_COOKIE_NAME,
    REFRESH_TOKEN_EXPIRE_MINUTES,
    TOKEN_COOKIE_NAME,
    SECRET_KEY,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_password_hash,
    revoke_token,
    revoke_user,
    verify_password,
    generate_password_reset_token,
    get_password_reset_token_expiry,
    RESET_TOKEN_EXPIRE_MINUTES,
)
from app.database import Base, SessionLocal, engine, get_db
from app.models import (
    Activity,
    UserActivity,
    LoginActivity,
    SecurityAlert,
    Alert,
    User,
    PasswordResetToken,
    AnomalyAlert,
    Tenant,
    TenantSubscription,
    TenantMLConfig,
)
from starlette.middleware.sessions import SessionMiddleware
from app.adaptive_auth.orchestrator import AdaptiveAuthOrchestrator
from app.adaptive_auth.risk_engine import compute_risk_score
from app.adaptive_auth.decision_engine import decision_from_risk

Base.metadata.create_all(bind=engine)

# when the application starts we may be running against an existing SQLite file
# that was created before certain columns (like risk_score) were added to the
# SQLAlchemy model.  create_all() does *not* alter existing tables, so we
# explicitly check and add any missing columns here to avoid OperationalError
# during normal requests.

def _ensure_schema_updates():
    insp = inspect(engine)
    if 'users' in insp.get_table_names():
        existing = {c['name'] for c in insp.get_columns('users')}
        # columns added over time; defaults chosen to match model definitions
        to_add = [
            ("risk_score", "FLOAT DEFAULT 0.0"),
            ("google_id", "VARCHAR(255)"),
            ("github_id", "VARCHAR(255)"),
            ("microsoft_id", "VARCHAR(255)"),
            ("is_active", "BOOLEAN DEFAULT 1"),
            ("status", "VARCHAR(20) DEFAULT 'Enabled'"),
            ("email_verified", "BOOLEAN DEFAULT 0"),
            ("is_suspicious", "BOOLEAN DEFAULT 0"),
            ("tenant_id", "VARCHAR(50) DEFAULT 'default'"),
            ("last_login", "DATETIME"),
            ("updated_at", "DATETIME"),
        ]
        with engine.begin() as conn:
            for col, definition in to_add:
                if col not in existing:
                    logger.info(f"Adding missing column '{col}' to users table")
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {definition}"))

            # normalize historical user rows with null status values
            conn.execute(text("UPDATE users SET status = 'Enabled' WHERE status IS NULL"))

    # check other tables for historically added columns
    if 'alerts' in insp.get_table_names():
        alert_cols = {c['name'] for c in insp.get_columns('alerts')}
        with engine.begin() as conn:
            if 'tenant_id' not in alert_cols:
                logger.info("Adding missing column 'tenant_id' to alerts table")
                conn.execute(text("ALTER TABLE alerts ADD COLUMN tenant_id VARCHAR(50) DEFAULT 'default'"))
            if 'ip_address' not in alert_cols:
                logger.info("Adding missing column 'ip_address' to alerts table")
                conn.execute(text("ALTER TABLE alerts ADD COLUMN ip_address VARCHAR(45)"))
            if 'feedback_status' not in alert_cols:
                logger.info("Adding missing column 'feedback_status' to alerts table")
                conn.execute(text("ALTER TABLE alerts ADD COLUMN feedback_status VARCHAR(20) DEFAULT 'pending'"))
            if 'feedback_notes' not in alert_cols:
                logger.info("Adding missing column 'feedback_notes' to alerts table")
                conn.execute(text("ALTER TABLE alerts ADD COLUMN feedback_notes TEXT"))

    if 'activities' in insp.get_table_names():
        act_cols = {c['name'] for c in insp.get_columns('activities')}
        with engine.begin() as conn:
            if 'tenant_id' not in act_cols:
                logger.info("Adding missing column 'tenant_id' to activities table")
                conn.execute(text("ALTER TABLE activities ADD COLUMN tenant_id VARCHAR(50) DEFAULT 'default'"))

    if 'security_alerts' in insp.get_table_names():
        security_cols = {c['name'] for c in insp.get_columns('security_alerts')}
        with engine.begin() as conn:
            if 'verdict' not in security_cols:
                logger.info("Adding missing column 'verdict' to security_alerts table")
                conn.execute(text("ALTER TABLE security_alerts ADD COLUMN verdict VARCHAR(20) DEFAULT 'pending'"))

# run the helper right away
_ensure_schema_updates()

app = FastAPI(title="CyberGuard UEBA Auth")
adaptive_auth = AdaptiveAuthOrchestrator()


@app.on_event("startup")
async def startup_log() -> None:
    print("UEBA Server Running Successfully")
    await adaptive_auth.start()


@app.on_event("shutdown")
async def shutdown_log() -> None:
    await adaptive_auth.stop()

# add CORS middleware for frontend applications
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv('CORS_ORIGINS', 'http://localhost').split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# mount static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# templates directory at project root
templates = Jinja2Templates(directory="templates")

ALLOWED_ROLES = {"user", "admin", "security_analyst", "threat_hunter"}

# configure OAuth client
if OAuth is not None:
    oauth = OAuth()
    oauth.register(
        name='google',
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )

    # GitHub OAuth configuration (see docs for setup steps)
    oauth.register(
        name='github',
        client_id=os.getenv('GITHUB_CLIENT_ID'),
        client_secret=os.getenv('GITHUB_CLIENT_SECRET'),
        access_token_url='https://github.com/login/oauth/access_token',
        authorize_url='https://github.com/login/oauth/authorize',
        api_base_url='https://api.github.com/',
        client_kwargs={'scope': 'user:email'},
    )
else:
    oauth = None


class RegisterPayload(BaseModel):
    email: EmailStr
    password: str
    confirmPassword: str
    role: str = "user"
    username: Optional[str] = None


class LoginPayload(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: str
    device_fingerprint: Optional[str] = None


class FeedbackData(BaseModel):
    alert_id: int
    status: str
    notes: str = ""


class SessionBehaviorPayload(BaseModel):
    mouse_movement_frequency: int = 0
    click_rate: int = 0
    api_request_frequency: int = 0
    failed_api_attempts: int = 0
    page_navigation_timing_ms: float = 0.0
    page_path: str = "/"
    captured_at: Optional[str] = None


class TenantCreatePayload(BaseModel):
    name: str
    region: str = "us-east-1"
    tier: str = "starter"


class TenantTierUpdatePayload(BaseModel):
    tier: str


class TenantMLTogglePayload(BaseModel):
    retraining_enabled: bool


class AlertVerdictPayload(BaseModel):
    verdict: str


def _is_html_request(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    content_type = request.headers.get("content-type", "")
    return (
        "text/html" in accept
        or "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    )


def _redirect_with_query(path: str, **params: str) -> RedirectResponse:
    cleaned = {k: v for k, v in params.items() if v}
    query = f"?{urlencode(cleaned)}" if cleaned else ""
    return RedirectResponse(url=f"{path}{query}", status_code=status.HTTP_302_FOUND)


def _set_auth_cookie(response, access_token: str, refresh_token: Optional[str] = None) -> None:
    # cookie `secure` flag toggled by environment variable so it can be true in production
    secure_cookie = os.getenv("SESSION_SECURE_COOKIE", "False").lower() in ("true", "1", "yes")
    response.set_cookie(
        key=TOKEN_COOKIE_NAME,
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=secure_cookie,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    if refresh_token:
        response.set_cookie(
            key=REFRESH_TOKEN_COOKIE_NAME,
            value=refresh_token,
            httponly=True,
            samesite="lax",
            secure=secure_cookie,
            max_age=REFRESH_TOKEN_EXPIRE_MINUTES * 60,
        )


def _mock_geo_location(ip_address: str) -> str:
    if not ip_address:
        return "unknown"
    if ip_address.startswith("10.") or ip_address.startswith("192.168.") or ip_address.startswith("127."):
        return "private_network"
    first_octet = int(ip_address.split(".")[0]) if "." in ip_address and ip_address.split(".")[0].isdigit() else 0
    if first_octet < 64:
        return "us-east"
    if first_octet < 128:
        return "eu-central"
    if first_octet < 192:
        return "ap-south"
    return "global-edge"


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _ip_is_private(ip_address: str) -> bool:
    try:
        return ipaddress.ip_address(ip_address).is_private
    except ValueError:
        return True


def _resolve_geo_from_ip(ip_address: str) -> dict[str, Any]:
    if not ip_address or _ip_is_private(ip_address):
        return {
            "country": "Private Network",
            "city": "Local",
            "latitude": None,
            "longitude": None,
        }

    providers = [
        f"https://ipapi.co/{ip_address}/json/",
        f"https://ipinfo.io/{ip_address}/json",
    ]
    for provider in providers:
        try:
            response = httpx.get(provider, timeout=2.5)
            if response.status_code != 200:
                continue
            data = response.json()
            if "ipapi.co" in provider:
                lat = _safe_float(data.get("latitude"))
                lon = _safe_float(data.get("longitude"))
                return {
                    "country": data.get("country_name") or data.get("country") or "Unknown",
                    "city": data.get("city") or "Unknown",
                    "latitude": lat,
                    "longitude": lon,
                }
            loc_value = data.get("loc", "")
            lat, lon = None, None
            if isinstance(loc_value, str) and "," in loc_value:
                lat_part, lon_part = loc_value.split(",", 1)
                lat = _safe_float(lat_part)
                lon = _safe_float(lon_part)
            return {
                "country": data.get("country") or "Unknown",
                "city": data.get("city") or "Unknown",
                "latitude": lat,
                "longitude": lon,
            }
        except Exception:
            continue
    return {"country": "Unknown", "city": "Unknown", "latitude": None, "longitude": None}


def _risk_severity(score: float) -> str:
    if score >= 71:
        return "Critical"
    if score >= 41:
        return "High"
    if score >= 21:
        return "Medium"
    return "Low"


def _create_security_alert(
    db: Session,
    *,
    user: User,
    alert_type: str,
    description: str,
    severity: str,
) -> None:
    db.add(
        SecurityAlert(
            user_id=user.id,
            alert_type=alert_type,
            description=description,
            severity=severity,
        )
    )


def _extract_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def _extract_device_info(request: Request, fallback: Optional[str] = None) -> str:
    return fallback or request.headers.get("x-device-fingerprint") or request.headers.get("user-agent") or "unknown_device"


def _create_login_alerts(
    db: Session,
    *,
    user: User,
    reasons: list[str],
    anomaly_score: float,
    is_anomaly: bool,
    risk_score: float,
    country: str,
) -> None:
    severity = _risk_severity(risk_score)
    for reason in reasons:
        alert_type = "login_risk"
        if "country" in reason.lower():
            alert_type = "new_country_login"
        elif "failed" in reason.lower():
            alert_type = "failed_login_attempts"
        elif "device" in reason.lower():
            alert_type = "new_device_login"
        _create_security_alert(
            db,
            user=user,
            alert_type=alert_type,
            description=f"{reason}. Country: {country}.",
            severity=severity,
        )

    if is_anomaly:
        db.add(
            AnomalyAlert(
                user_id=user.id,
                anomaly_score=anomaly_score,
                risk_level=_risk_severity(max(risk_score, anomaly_score)),
            )
        )
        _create_security_alert(
            db,
            user=user,
            alert_type="anomaly_detected",
            description=f"Suspicious login behaviour detected by Isolation Forest (score={anomaly_score:.2f}).",
            severity=_risk_severity(max(risk_score, anomaly_score)),
        )


def _rule_based_risk_score(
    db: Session,
    *,
    user: User,
    ip_address: str,
    country: str,
    device_fingerprint: str,
    failed_login_attempts: int,
    login_timestamp: datetime,
) -> tuple[float, list[str]]:
    risk = 0.0
    reasons: list[str] = []

    recent_success = (
        db.query(LoginActivity)
        .filter(LoginActivity.user_id == user.id)
        .order_by(LoginActivity.login_time.desc())
        .limit(50)
        .all()
    )

    if recent_success:
        known_devices = {r.device_info for r in recent_success if r.device_info}
        known_countries = {r.country for r in recent_success if r.country}
        latest = recent_success[0]

        if device_fingerprint not in known_devices:
            risk += 20
            reasons.append("New device login")

        if country and country not in known_countries and country != "Private Network":
            risk += 40
            reasons.append("Login from new country")

        if latest.ip_address and latest.ip_address != ip_address:
            risk += 10
            reasons.append("IP address changed")

        if latest.country and latest.country != country:
            risk += 10
            reasons.append("Location changed")
    else:
        risk += 10
        reasons.append("First observed login baseline")

    if failed_login_attempts >= 3:
        risk += 30
        reasons.append("Multiple failed logins")

    if login_timestamp.hour < 6 or login_timestamp.hour > 22:
        risk += 10
        reasons.append("Login at unusual time")

    recent_hour_logins = (
        db.query(LoginActivity)
        .filter(
            LoginActivity.user_id == user.id,
            LoginActivity.login_time >= datetime.utcnow() - timedelta(hours=1),
        )
        .count()
    )
    if recent_hour_logins >= 6:
        risk += 10
        reasons.append("Unusual login frequency")

    return min(100.0, risk), reasons


def _build_login_feature_vectors(rows: list[LoginActivity]) -> np.ndarray:
    if not rows:
        return np.empty((0, 6))
    rows = sorted(rows, key=lambda item: item.login_time or datetime.utcnow())
    vectors = []
    for idx, row in enumerate(rows):
        prev = rows[idx - 1] if idx > 0 else None
        login_dt = row.login_time or datetime.utcnow()
        hour = float(login_dt.hour)
        delta_minutes = 60.0
        ip_change = 0.0
        device_change = 0.0
        location_change = 0.0
        if prev and prev.login_time:
            delta_minutes = max(1.0, min(1440.0, (login_dt - prev.login_time).total_seconds() / 60.0))
            ip_change = 1.0 if row.ip_address and row.ip_address != prev.ip_address else 0.0
            device_change = 1.0 if row.device_info and row.device_info != prev.device_info else 0.0
            location_change = 1.0 if row.country and row.country != prev.country else 0.0
        recent_freq = 1.0
        for back in range(max(0, idx - 12), idx):
            if rows[back].login_time and (login_dt - rows[back].login_time).total_seconds() <= 3600:
                recent_freq += 1.0
        vectors.append([hour, delta_minutes, ip_change, device_change, location_change, recent_freq])
    return np.asarray(vectors, dtype=float)


def _compute_isolation_forest_anomaly(
    db: Session,
    *,
    user: User,
    probe: LoginActivity,
) -> tuple[float, bool]:
    history = (
        db.query(LoginActivity)
        .filter(LoginActivity.user_id == user.id)
        .order_by(LoginActivity.login_time.desc())
        .limit(120)
        .all()
    )
    all_rows = list(history)
    all_rows.append(probe)
    vectors = _build_login_feature_vectors(all_rows)
    if vectors.shape[0] < 10:
        return 0.0, False
    train_vectors = vectors[:-1]
    probe_vector = vectors[-1:]
    model = IsolationForest(
        n_estimators=120,
        contamination=0.12,
        random_state=42,
    )
    model.fit(train_vectors)
    anomaly_value = float(-model.decision_function(probe_vector)[0])
    is_anomaly = int(model.predict(probe_vector)[0]) == -1
    normalized_score = max(0.0, min(100.0, anomaly_value * 100.0))
    return normalized_score, is_anomaly


def role_required(*roles: str):
    allowed = {r.lower() for r in roles}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if (current_user.role or "").lower() not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient role permissions")
        return current_user

    return dependency


@app.middleware("http")
async def log_requests(request: Request, call_next):
    # simple logging middleware to capture incoming requests and unexpected errors
    logger.info(f"{request.method} {request.url}")
    try:
        response = await call_next(request)
        return response
    except Exception:
        logger.exception("Unhandled exception while processing request")
        # re‑raise so FastAPI can return proper 500 response
        raise

@app.middleware("http")
async def auth_cookie_middleware(request: Request, call_next):
    request.state.user = None
    token = request.cookies.get(TOKEN_COOKIE_NAME)
    if token:
        payload = decode_access_token(token)
        if payload:
            email = payload.get("sub")
            if email:
                db = SessionLocal()
                try:
                    user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
                    if user and not user.is_active:
                        revoke_user(user.id)
                        user = None
                    if user and user.id in adaptive_auth.invalidated_users:
                        revoke_user(user.id)
                        user = None
                    if user and user.id in adaptive_auth.locked_accounts:
                        lock_until_raw = adaptive_auth.locked_accounts[user.id].get("lock_until")
                        if lock_until_raw:
                            try:
                                lock_until = datetime.fromisoformat(str(lock_until_raw).replace("Z", "+00:00"))
                                if lock_until.tzinfo is not None:
                                    lock_until = lock_until.astimezone(timezone.utc).replace(tzinfo=None)
                                if datetime.utcnow() < lock_until:
                                    revoke_user(user.id)
                                    user = None
                                else:
                                    adaptive_auth.locked_accounts.pop(user.id, None)
                            except ValueError:
                                revoke_user(user.id)
                                user = None
                    request.state.user = user
                finally:
                    db.close()
    response = await call_next(request)
    return response


def get_current_user(request: Request) -> User:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized access",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled. Contact administrator.",
        )
    return user


def get_current_user_optional(request: Request) -> Optional[User]:
    user = getattr(request.state, "user", None)
    if user and not user.is_active:
        return None
    return user


def _create_user_or_400(
    db: Session,
    *,
    email: str,
    password: str,
    confirm_password: str,
    role: str = "user",
    username: Optional[str] = None,
) -> User:
    normalized_email = email.strip().lower()
    normalized_username = (username or "").strip()
    normalized_role = (role or "user").strip().lower()

    if len(normalized_username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 3 characters",
        )

    if password != confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        )
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )
    if normalized_role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role selected",
        )

    existing_email = (
        db.query(User).filter(func.lower(User.email) == normalized_email).first()
    )
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )

    username_seed = normalized_username.lower() or normalized_email
    username_value = username_seed
    suffix = 1
    while db.query(User).filter(func.lower(User.username) == username_value).first():
        username_value = f"{username_seed}_{suffix}"
        suffix += 1

    new_user = User(
        username=username_value,
        email=normalized_email,
        hashed_password=get_password_hash(password),
        role=normalized_role,
        tenant_id="default",
        status="Enabled",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def _authenticate_user_or_401(db: Session, identifier: str, password: str) -> User:
    normalized = identifier.strip().lower()
    user = (
        db.query(User)
        .filter(
            or_(
                func.lower(User.email) == normalized,
                func.lower(User.username) == normalized,
            )
        )
        .first()
    )
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled. Contact administrator.",
        )
    return user


def _get_user_by_identifier(db: Session, identifier: str) -> Optional[User]:
    normalized = (identifier or "").strip().lower()
    if not normalized:
        return None
    return (
        db.query(User)
        .filter(
            or_(
                func.lower(User.email) == normalized,
                func.lower(User.username) == normalized,
            )
        )
        .first()
    )


def _record_login_activity(
    db: Session,
    *,
    user: User,
    ip_address: Optional[str],
    device_fingerprint: Optional[str],
    status_value: str,
    risk_score: float = 0.0,
    country: Optional[str] = None,
    city: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> None:
    location = _mock_geo_location(ip_address or "")
    activity = Activity(
        user_id=user.id,
        tenant_id=user.tenant_id or "default",
        ip_address=ip_address,
        device_info=device_fingerprint,
        location=location,
        status=status_value,
    )
    db.add(activity)
    db.add(
        UserActivity(
            user_id=user.id,
            ip_address=ip_address,
            device_info=device_fingerprint,
            location=location,
            activity_type=f"login_{status_value}",
            risk_score=float(risk_score or 0.0),
        )
    )
    db.add(
        LoginActivity(
            user_id=user.id,
            ip_address=ip_address,
            country=country or "Unknown",
            city=city or "Unknown",
            latitude=latitude,
            longitude=longitude,
            device_info=device_fingerprint,
            risk_score=float(risk_score or 0.0),
        )
    )
    db.commit()


def _record_user_activity(
    db: Session,
    *,
    user: User,
    activity_type: str,
    request: Optional[Request] = None,
    ip_address: Optional[str] = None,
    device_info: Optional[str] = None,
    risk_score: float = 0.0,
) -> None:
    resolved_ip = ip_address or (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if request
        else ""
    ) or (request.client.host if request and request.client else "unknown")
    resolved_device = device_info or (
        request.headers.get("user-agent", "unknown_device") if request else "unknown_device"
    )
    db.add(
        UserActivity(
            user_id=user.id,
            ip_address=resolved_ip,
            device_info=resolved_device,
            location=_mock_geo_location(resolved_ip),
            activity_type=activity_type,
            risk_score=float(risk_score or 0.0),
        )
    )
    db.commit()


def _detect_unusual_login(
    db: Session,
    *,
    user: User,
    ip_address: str,
    device_fingerprint: str,
    risk_score: float,
) -> None:
    recent_window = datetime.utcnow() - timedelta(hours=24)
    recent_ips = (
        db.query(UserActivity.ip_address)
        .filter(
            UserActivity.user_id == user.id,
            UserActivity.activity_type == "login_success",
            UserActivity.login_time >= recent_window,
        )
        .distinct()
        .all()
    )
    unique_recent_ips = {ip for (ip,) in recent_ips if ip}
    is_new_ip = ip_address not in unique_recent_ips

    recent_devices = (
        db.query(UserActivity.device_info)
        .filter(
            UserActivity.user_id == user.id,
            UserActivity.activity_type == "login_success",
            UserActivity.login_time >= recent_window,
        )
        .distinct()
        .all()
    )
    unique_recent_devices = {d for (d,) in recent_devices if d}
    is_new_device = device_fingerprint not in unique_recent_devices

    if is_new_ip and len(unique_recent_ips) >= 2:
        user.is_suspicious = True
        db.add(
            Alert(
                user_id=user.id,
                tenant_id=user.tenant_id or "default",
                anomaly_score=max(float(risk_score or 0.0), 72.0),
                risk_level="High",
                ip_address=ip_address,
            )
        )
        db.add(
            UserActivity(
                user_id=user.id,
                ip_address=ip_address,
                device_info=device_fingerprint,
                location=_mock_geo_location(ip_address),
                activity_type="suspicious_multi_ip_login",
                risk_score=max(float(risk_score or 0.0), 72.0),
            )
        )
        _create_security_alert(
            db,
            user=user,
            alert_type="multi_ip_login",
            description="Suspicious login behaviour detected: login from multiple IP addresses.",
            severity="High",
        )
    elif is_new_device:
        db.add(
            UserActivity(
                user_id=user.id,
                ip_address=ip_address,
                device_info=device_fingerprint,
                location=_mock_geo_location(ip_address),
                activity_type="new_device_login",
                risk_score=max(float(risk_score or 0.0), 45.0),
            )
        )
        _create_security_alert(
            db,
            user=user,
            alert_type="new_device_login",
            description="User logged in from a new device.",
            severity="Medium",
        )
    db.commit()


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "UEBA-Backend"}


@app.get("/health")
def simple_health_check():
    """Simple health check."""
    return "OK"


@app.get("/")
async def home_page(request: Request, current_user: Optional[User] = Depends(get_current_user_optional)):
    return templates.TemplateResponse("home.html", {"request": request, "current_user": current_user})


@app.get("/home")
async def home_alias(request: Request, current_user: Optional[User] = Depends(get_current_user_optional)):
    return templates.TemplateResponse("home.html", {"request": request, "current_user": current_user})


@app.get("/login")
async def login_page(request: Request, current_user: Optional[User] = Depends(get_current_user_optional)):
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "current_user": current_user,
            "error": request.query_params.get("error", ""),
            "success": request.query_params.get("success", ""),
            "mode": request.query_params.get("mode", "login"),
        },
    )


@app.get("/signup")
async def signup_page(request: Request):
    current_user = getattr(request.state, "user", None)
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        "signup.html",
        {
            "request": request,
            "current_user": current_user,
            "error": request.query_params.get("error", ""),
        },
    )


@app.post("/signup")
async def signup_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirmPassword: Optional[str] = Form(None),
    confirm_password: Optional[str] = Form(None),
    username: str = Form(...),
    role: str = Form("user"),
    db: Session = Depends(get_db),
):
    password_confirmation = confirmPassword or confirm_password or ""
    try:
        _create_user_or_400(
            db,
            email=email,
            password=password,
            confirm_password=password_confirmation,
            username=username,
            role=role,
        )
    except HTTPException as exc:
        logger.warning(f"Signup failed: {exc.detail}")
        if _is_html_request(request):
            return _redirect_with_query("/signup", error=str(exc.detail))
        raise
    except Exception as exc:
        logger.exception("Unexpected error during signup")
        db.rollback()
        if _is_html_request(request):
            return _redirect_with_query(
                "/signup", error="Registration failed. Please try again."
            )
        raise HTTPException(status_code=500, detail="Registration failed")

    if _is_html_request(request):
        return _redirect_with_query("/login", success="Account created. Please log in.")
    return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "User created"})


# simple in-memory rate limiter (per-ip; replace with redis/slowapi for production)
_login_attempts: dict = {}
import time

def _rate_limit(ip: str, limit: int = 5, window: int = 60) -> bool:
    now = time.time()
    stamps = _login_attempts.get(ip, [])
    stamps = [t for t in stamps if now - t < window]
    stamps.append(now)
    _login_attempts[ip] = stamps
    return len(stamps) <= limit


@app.post("/login")
async def login_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    client_ip = _extract_client_ip(request)
    device_info = _extract_device_info(request)
    if not _rate_limit(client_ip):
        logger.warning(f"Rate limit hit for {client_ip}")
        matched_user = _get_user_by_identifier(db, email)
        if matched_user:
            _create_security_alert(
                db,
                user=matched_user,
                alert_type="rate_limited_login",
                description="Multiple failed login attempts detected from same IP.",
                severity="High",
            )
            db.commit()
        if _is_html_request(request):
            return _redirect_with_query("/login", error="Too many attempts, please wait a minute.")
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                             detail="Too many login attempts")

    try:
        user = _authenticate_user_or_401(db, email, password)
    except HTTPException as exc:
        logger.warning(f"Login failed for {email}: {exc.detail}")
        matched_user = _get_user_by_identifier(db, email)
        if matched_user:
            event_type = "login_failed_disabled_account" if exc.status_code == status.HTTP_403_FORBIDDEN else "login_failed"
            _record_login_activity(
                db,
                user=matched_user,
                ip_address=client_ip,
                device_fingerprint=device_info,
                status_value="failed",
                risk_score=float(matched_user.risk_score or 0.0),
            )
            failed_attempts = (
                db.query(Activity)
                .filter(
                    Activity.user_id == matched_user.id,
                    Activity.status == "failed",
                    Activity.login_time >= datetime.utcnow() - timedelta(hours=24),
                )
                .count()
            )
            if failed_attempts >= 3:
                _create_security_alert(
                    db,
                    user=matched_user,
                    alert_type="failed_login_attempts",
                    description="Multiple failed login attempts detected.",
                    severity="High",
                )
            _record_user_activity(
                db,
                user=matched_user,
                activity_type=event_type,
                request=request,
                risk_score=float(matched_user.risk_score or 0.0),
            )
            db.commit()
        if _is_html_request(request):
            if exc.status_code == status.HTTP_403_FORBIDDEN:
                return _redirect_with_query(
                    "/login",
                    error="Your account has been disabled by the administrator.",
                )
            return _redirect_with_query("/login", error="Invalid email/password")
        raise
    except Exception:
        logger.exception("Unexpected error during login")
        raise

    geo = _resolve_geo_from_ip(client_ip)
    failed_login_attempts = (
        db.query(Activity)
        .filter(
            Activity.user_id == user.id,
            Activity.status == "failed",
            Activity.login_time >= datetime.utcnow() - timedelta(hours=24),
        )
        .count()
    )
    login_timestamp = datetime.utcnow()
    rule_risk, reasons = _rule_based_risk_score(
        db,
        user=user,
        ip_address=client_ip,
        country=geo["country"],
        device_fingerprint=device_info,
        failed_login_attempts=failed_login_attempts,
        login_timestamp=login_timestamp,
    )
    probe = LoginActivity(
        user_id=user.id,
        ip_address=client_ip,
        country=geo["country"],
        city=geo["city"],
        latitude=geo["latitude"],
        longitude=geo["longitude"],
        device_info=device_info,
        login_time=login_timestamp,
        risk_score=rule_risk,
    )
    anomaly_score, is_anomaly = _compute_isolation_forest_anomaly(db, user=user, probe=probe)
    final_risk = max(float(user.risk_score or 0.0), rule_risk, anomaly_score)
    user.risk_score = final_risk
    user.is_suspicious = final_risk >= 71

    access_token = create_access_token(data={"sub": user.email, "uid": user.id, "role": user.role})
    refresh_token = create_refresh_token(data={"sub": user.email, "uid": user.id, "role": user.role})
    response = (
        RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
        if _is_html_request(request)
        else JSONResponse(content={"message": "Login successful"})
    )
    user.last_login = login_timestamp
    user.status = "Enabled" if user.is_active else "Disabled"
    db.commit()
    _record_login_activity(
        db,
        user=user,
        ip_address=client_ip,
        device_fingerprint=device_info,
        status_value="success",
        risk_score=final_risk,
        country=geo["country"],
        city=geo["city"],
        latitude=geo["latitude"],
        longitude=geo["longitude"],
    )
    _create_login_alerts(
        db,
        user=user,
        reasons=reasons,
        anomaly_score=anomaly_score,
        is_anomaly=is_anomaly,
        risk_score=final_risk,
        country=geo["country"],
    )
    _record_user_activity(
        db,
        user=user,
        activity_type="login_success",
        request=request,
        risk_score=final_risk,
    )
    db.commit()
    _set_auth_cookie(response, access_token, refresh_token)
    return response


@app.get("/logout")
async def logout_page(request: Request, db: Session = Depends(get_db)):
    current_user = getattr(request.state, "user", None)
    if current_user:
        _record_user_activity(
            db,
            user=current_user,
            activity_type="logout",
            request=request,
            risk_score=float(current_user.risk_score or 0.0),
        )
    token = request.cookies.get(TOKEN_COOKIE_NAME)
    if token:
        revoke_token(token)
    request.session.clear()
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(TOKEN_COOKIE_NAME)
    response.delete_cookie(REFRESH_TOKEN_COOKIE_NAME)
    return response


@app.post("/api/register")
def register(payload: RegisterPayload, db: Session = Depends(get_db)):
    try:
        _create_user_or_400(
            db,
            email=payload.email,
            password=payload.password,
            confirm_password=payload.confirmPassword,
            role=payload.role,
            username=payload.username,
        )
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Registration failed")

    return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "User created"})


@app.post("/api/login")
async def login(payload: LoginPayload, request: Request, db: Session = Depends(get_db)):
    identifier = payload.email or payload.username
    if not identifier:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email or username is required")

    ip_address = _extract_client_ip(request)
    device_fingerprint = _extract_device_info(request, payload.device_fingerprint)
    geo = _resolve_geo_from_ip(ip_address)

    if not _rate_limit(ip_address):
        matched = _get_user_by_identifier(db, identifier)
        if matched:
            _create_security_alert(
                db,
                user=matched,
                alert_type="rate_limited_login",
                description="Multiple failed login attempts detected from same IP.",
                severity="High",
            )
            db.commit()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")

    matched_user = _get_user_by_identifier(db, identifier)
    login_timestamp = datetime.now(timezone.utc)
    correlation_id = str(uuid4())
    geo_location = _mock_geo_location(ip_address)

    if matched_user and not matched_user.is_active:
        _record_user_activity(
            db,
            user=matched_user,
            activity_type="login_failed_disabled_account",
            request=request,
            ip_address=ip_address,
            device_info=device_fingerprint,
            risk_score=float(matched_user.risk_score or 0.0),
        )
        return JSONResponse(
            status_code=403,
            content={
                "status": "blocked",
                "detail": "Account disabled. Contact administrator.",
            },
        )

    if matched_user and matched_user.id in adaptive_auth.locked_accounts:
        lock_data = adaptive_auth.locked_accounts[matched_user.id]
        lock_until_raw = lock_data.get("lock_until")
        if lock_until_raw:
            try:
                lock_until = datetime.fromisoformat(str(lock_until_raw).replace("Z", "+00:00"))
                if lock_until.tzinfo is not None:
                    lock_until = lock_until.astimezone(timezone.utc).replace(tzinfo=None)
                if datetime.utcnow() < lock_until:
                    return JSONResponse(
                        status_code=423,
                        content={
                            "status": "blocked",
                            "detail": "Account temporarily locked due to active threat session.",
                            "lock_until": lock_until_raw,
                        },
                    )
                adaptive_auth.locked_accounts.pop(matched_user.id, None)
            except ValueError:
                return JSONResponse(status_code=423, content={"status": "blocked", "detail": "Account locked"})

    if not matched_user or not verify_password(payload.password, matched_user.hashed_password):
        if matched_user:
            _record_login_activity(
                db,
                user=matched_user,
                ip_address=ip_address,
                device_fingerprint=device_fingerprint,
                status_value="failed",
                risk_score=float(matched_user.risk_score or 0.0),
                country=geo["country"],
                city=geo["city"],
                latitude=geo["latitude"],
                longitude=geo["longitude"],
            )
            failed_attempts = (
                db.query(Activity)
                .filter(
                    Activity.user_id == matched_user.id,
                    Activity.status == "failed",
                    Activity.login_time >= datetime.utcnow() - timedelta(hours=24),
                )
                .count()
            )
            if failed_attempts >= 3:
                _create_security_alert(
                    db,
                    user=matched_user,
                    alert_type="failed_login_attempts",
                    description="Multiple failed login attempts detected.",
                    severity="High",
                )
                db.commit()
        else:
            failed_attempts = 1

        login_event = {
            "correlation_id": correlation_id,
            "user_id": matched_user.id if matched_user else -1,
            "tenant_id": matched_user.tenant_id if matched_user else "default",
            "email": identifier.lower(),
            "ip_address": ip_address,
            "device_fingerprint": device_fingerprint,
            "login_timestamp": login_timestamp.isoformat(),
            "geo_location": geo_location,
            "failed_login_attempts": failed_attempts,
            "previous_risk_score": float(matched_user.risk_score if matched_user else 0.0),
            "authentication_status": "failed",
        }
        await adaptive_auth.publish_login_event(login_event)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    failed_login_attempts = (
        db.query(Activity)
        .filter(
            Activity.user_id == matched_user.id,
            Activity.status == "failed",
            Activity.login_time >= datetime.utcnow() - timedelta(hours=24),
        )
        .count()
    )
    elapsed_hours = 1.0
    if matched_user.updated_at:
        elapsed_hours = max(
            0.0,
            (login_timestamp.replace(tzinfo=None) - matched_user.updated_at).total_seconds() / 3600.0,
        )

    login_event = {
        "correlation_id": correlation_id,
        "user_id": matched_user.id,
        "tenant_id": matched_user.tenant_id or "default",
        "email": matched_user.email,
        "ip_address": ip_address,
        "device_fingerprint": device_fingerprint,
        "login_timestamp": login_timestamp.isoformat(),
        "geo_location": geo_location,
        "failed_login_attempts": failed_login_attempts,
        "previous_risk_score": float(matched_user.risk_score or 0.0),
        "elapsed_hours_since_last_login": elapsed_hours,
        "authentication_status": "credentials_valid",
    }
    await adaptive_auth.publish_login_event(login_event)

    risk_result = await adaptive_auth.wait_for_risk(correlation_id, timeout=5.0)
    if risk_result:
        risk_score = float(risk_result.get("risk_score", 0.0))
        status_value = risk_result.get("status", decision_from_risk(risk_score))
    else:
        # Fallback decision path if Kafka/risk services are unavailable.
        risk_score = compute_risk_score(
            previous_risk_score=float(matched_user.risk_score or 0.0),
            anomaly_score=0.0,
            failed_login_attempts=failed_login_attempts,
            elapsed_hours_since_last_login=elapsed_hours,
        )
        status_value = decision_from_risk(risk_score)

    baseline_login_ts = login_timestamp.astimezone(timezone.utc).replace(tzinfo=None)
    rule_risk, reasons = _rule_based_risk_score(
        db,
        user=matched_user,
        ip_address=ip_address,
        country=geo["country"],
        device_fingerprint=device_fingerprint,
        failed_login_attempts=failed_login_attempts,
        login_timestamp=baseline_login_ts,
    )
    probe = LoginActivity(
        user_id=matched_user.id,
        ip_address=ip_address,
        country=geo["country"],
        city=geo["city"],
        latitude=geo["latitude"],
        longitude=geo["longitude"],
        device_info=device_fingerprint,
        login_time=baseline_login_ts,
        risk_score=max(risk_score, rule_risk),
    )
    anomaly_score, is_anomaly = _compute_isolation_forest_anomaly(db, user=matched_user, probe=probe)
    risk_score = max(risk_score, rule_risk, anomaly_score)

    matched_user.risk_score = risk_score
    matched_user.is_suspicious = risk_score >= 71
    db.commit()

    if status_value == "blocked":
        _record_login_activity(
            db,
            user=matched_user,
            ip_address=ip_address,
            device_fingerprint=device_fingerprint,
            status_value="blocked",
            risk_score=risk_score,
            country=geo["country"],
            city=geo["city"],
            latitude=geo["latitude"],
            longitude=geo["longitude"],
        )
        db.add(
            Alert(
                user_id=matched_user.id,
                anomaly_score=risk_score,
                risk_level="High",
                ip_address=ip_address,
                tenant_id=matched_user.tenant_id or "default",
            )
        )
        _create_security_alert(
            db,
            user=matched_user,
            alert_type="suspicious_login_behaviour",
            description="Suspicious login behaviour detected.",
            severity="Critical",
        )
        db.commit()
        return JSONResponse(status_code=403, content={"status": "blocked", "risk_score": risk_score})

    if status_value == "2fa_required":
        _record_login_activity(
            db,
            user=matched_user,
            ip_address=ip_address,
            device_fingerprint=device_fingerprint,
            status_value="2fa_required",
            risk_score=risk_score,
            country=geo["country"],
            city=geo["city"],
            latitude=geo["latitude"],
            longitude=geo["longitude"],
        )
        return JSONResponse(status_code=202, content={"status": "2fa_required", "risk_score": risk_score})

    access_token = create_access_token(
        data={"sub": matched_user.email, "uid": matched_user.id, "role": matched_user.role}
    )
    refresh_token = create_refresh_token(
        data={"sub": matched_user.email, "uid": matched_user.id, "role": matched_user.role}
    )
    response = JSONResponse(content={"status": "allowed", "risk_score": risk_score})
    _set_auth_cookie(response, access_token, refresh_token)
    adaptive_auth.invalidated_users.pop(matched_user.id, None)
    matched_user.last_login = baseline_login_ts
    matched_user.status = "Enabled" if matched_user.is_active else "Disabled"
    db.commit()
    _detect_unusual_login(
        db,
        user=matched_user,
        ip_address=ip_address,
        device_fingerprint=device_fingerprint,
        risk_score=risk_score,
    )
    _record_login_activity(
        db,
        user=matched_user,
        ip_address=ip_address,
        device_fingerprint=device_fingerprint,
        status_value="success",
        risk_score=risk_score,
        country=geo["country"],
        city=geo["city"],
        latitude=geo["latitude"],
        longitude=geo["longitude"],
    )
    _create_login_alerts(
        db,
        user=matched_user,
        reasons=reasons,
        anomaly_score=anomaly_score,
        is_anomaly=is_anomaly,
        risk_score=risk_score,
        country=geo["country"],
    )
    db.commit()
    return response


@app.post("/api/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    current_user = getattr(request.state, "user", None)
    if current_user:
        _record_user_activity(
            db,
            user=current_user,
            activity_type="logout",
            request=request,
            risk_score=float(current_user.risk_score or 0.0),
        )
    token = request.cookies.get(TOKEN_COOKIE_NAME)
    if token:
        revoke_token(token)
    response = JSONResponse(content={"message": "Logout successful"})
    # API clients may clear via cookie lifecycle, but token revocation is handled by cookie middleware checks.
    response.delete_cookie(TOKEN_COOKIE_NAME)
    response.delete_cookie(REFRESH_TOKEN_COOKIE_NAME)
    return response


@app.get("/api/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "role": current_user.role,
    }


@app.post("/api/token/refresh")
def refresh_token(request: Request, db: Session = Depends(get_db)):
    refresh = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    if not refresh:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    payload = decode_refresh_token(refresh)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    email = payload.get("sub")
    user = db.query(User).filter(func.lower(User.email) == str(email).lower()).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    new_access_token = create_access_token(data={"sub": user.email, "uid": user.id, "role": user.role})
    response = JSONResponse(content={"status": "refreshed"})
    _set_auth_cookie(response, new_access_token, refresh)
    return response


@app.get("/api/auth/risk")
def get_auth_risk(current_user: User = Depends(get_current_user)):
    latest = adaptive_auth.latest_risk_by_user.get(current_user.id, {})
    latest_score = float(latest.get("risk_score", current_user.risk_score or 0.0))
    alerts = adaptive_auth.high_risk_alerts.get(current_user.id, [])
    return {
        "risk_score": latest_score,
        "high_risk_alert": latest_score > 70,
        "latest_status": latest.get("status", "allowed"),
        "alerts": alerts[-5:],
    }


@app.get("/api/session-threats")
def get_session_threats(current_user: User = Depends(get_current_user)):
    invalidation = adaptive_auth.invalidated_users.get(current_user.id)
    lock_data = adaptive_auth.locked_accounts.get(current_user.id)
    return {
        "session_invalidated": bool(invalidation),
        "account_locked": bool(lock_data),
        "invalidation_event": invalidation,
        "lock_event": lock_data,
    }


@app.post("/api/session-event")
async def ingest_session_event(
    payload: SessionBehaviorPayload,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    event = {
        "correlation_id": str(uuid4()),
        "user_id": current_user.id,
        "tenant_id": current_user.tenant_id or "default",
        "email": current_user.email,
        "ip_address": request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown"),
        "mouse_movement_frequency": payload.mouse_movement_frequency,
        "click_rate": payload.click_rate,
        "api_request_frequency": payload.api_request_frequency,
        "failed_api_attempts": payload.failed_api_attempts,
        "page_navigation_timing_ms": payload.page_navigation_timing_ms,
        "page_path": payload.page_path,
        "captured_at": payload.captured_at or datetime.utcnow().isoformat(),
    }
    await adaptive_auth.publish_session_event(event)
    return {"status": "accepted"}


@app.websocket("/ws/risk-updates")
async def ws_risk_updates(websocket: WebSocket):
    token = websocket.cookies.get(TOKEN_COOKIE_NAME)
    payload = decode_access_token(token) if token else None
    if not payload:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    queue = await adaptive_auth.subscribe()
    try:
        while True:
            payload = await queue.get()
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        adaptive_auth.unsubscribe(queue)
    except Exception:
        adaptive_auth.unsubscribe(queue)


@app.get("/dashboard")
async def serve_dashboard(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": current_user, "current_user": current_user},
    )


@app.get("/api/dashboard/stats")
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    since = datetime.utcnow() - timedelta(hours=24)
    total_users = db.query(User).count()
    active_users = (
        db.query(User)
        .filter(User.is_active == True, User.last_login >= since)  # noqa: E712
        .count()
    )
    detected_anomalies = (
        db.query(LoginActivity)
        .filter(LoginActivity.login_time >= since, LoginActivity.risk_score >= 71)
        .count()
    )
    security_alerts = db.query(SecurityAlert).filter(SecurityAlert.timestamp >= since).count()
    return {
        "total_users": total_users,
        "active_users": active_users,
        "detected_anomalies": detected_anomalies,
        "security_alerts": security_alerts,
        # backwards compatibility
        "users": total_users,
        "signals": db.query(Activity).count(),
        "alerts": security_alerts,
    }


@app.get("/api/dashboard/activity")
def get_activity_by_hour(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    since = datetime.utcnow() - timedelta(hours=24)
    results = (
        db.query(func.strftime("%H", LoginActivity.login_time).label("hour"), func.count(LoginActivity.id))
        .filter(LoginActivity.login_time >= since)
        .group_by("hour")
        .all()
    )
    counts = {int(row[0]): row[1] for row in results}
    labels = [f"{h:02d}:00" for h in range(24)]
    values = [counts.get(h, 0) for h in range(24)]
    return {"labels": labels, "values": values}


@app.get("/api/dashboard/risk-distribution")
def get_risk_distribution(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    users = db.query(User).all()
    buckets = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
    for user in users:
        buckets[_risk_severity(float(user.risk_score or 0.0))] += 1
    return buckets


@app.get("/api/dashboard/alert-severity")
def get_alert_severity_distribution(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    since = datetime.utcnow() - timedelta(days=7)
    rows = (
        db.query(SecurityAlert.severity, func.count(SecurityAlert.id))
        .filter(SecurityAlert.timestamp >= since)
        .group_by(SecurityAlert.severity)
        .all()
    )
    counts = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
    for severity, total in rows:
        if severity in counts:
            counts[severity] = int(total)
    return counts


@app.get("/api/dashboard/login-map")
def get_login_map(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    activities = (
        db.query(LoginActivity)
        .order_by(LoginActivity.login_time.desc())
        .limit(250)
        .all()
    )
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "username": row.user.username if row.user else f"user-{row.user_id}",
            "ip_address": row.ip_address or "unknown",
            "country": row.country or "Unknown",
            "city": row.city or "Unknown",
            "latitude": row.latitude,
            "longitude": row.longitude,
            "risk_score": round(float(row.risk_score or 0.0), 2),
            "suspicious": float(row.risk_score or 0.0) >= 41,
            "login_time": row.login_time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for row in activities
        if row.latitude is not None and row.longitude is not None
    ]


@app.get("/api/dashboard/recent-login-activity")
def get_recent_login_activity(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.query(LoginActivity).order_by(LoginActivity.login_time.desc()).limit(30).all()
    return [
        {
            "id": row.id,
            "username": row.user.username if row.user else f"user-{row.user_id}",
            "ip_address": row.ip_address or "unknown",
            "country": row.country or "Unknown",
            "city": row.city or "Unknown",
            "device_info": row.device_info or "unknown_device",
            "risk_score": round(float(row.risk_score or 0.0), 2),
            "login_time": row.login_time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for row in rows
    ]


@app.get("/api/dashboard/security-alerts")
def get_security_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.query(SecurityAlert).order_by(SecurityAlert.timestamp.desc()).limit(40).all()
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "username": row.user.username if row.user else f"user-{row.user_id}",
            "alert_type": row.alert_type,
            "description": row.description,
            "severity": row.severity,
            "verdict": row.verdict or "pending",
            "timestamp": row.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for row in rows
    ]


@app.get("/api/dashboard/alerts")
def get_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_security_alerts(db=db, current_user=current_user)


@app.get("/api/anomalies")
def get_anomalies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return suspicious activities detected by the isolation forest."""
    # restrict admin only
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    anomalies = db.query(AnomalyAlert).order_by(AnomalyAlert.timestamp.desc()).limit(50).all()
    return [
        {
            "id": a.id,
            "username": a.user.username,
            "score": round(a.anomaly_score, 4),
            "level": a.risk_level,
            "time": a.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for a in anomalies
    ]


@app.get("/api/risk/user-risk")
def get_user_risk(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    users = db.query(User).all()
    risk_data = []
    for user in users:
        score = user.risk_score
        classification = "Low"
        if score > 80:
            classification = "Critical"
        elif score > 60:
            classification = "High"
        elif score > 30:
            classification = "Medium"
        risk_data.append(
            {
                "username": user.username,
                "risk_score": round(score, 2),
                "risk_level": classification,
            }
        )
    return risk_data


@app.post("/api/ml/feedback")
def submit_feedback(
    data: FeedbackData,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.status not in ["false_positive", "confirmed"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    alert = db.query(Alert).filter(Alert.id == data.alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.feedback_status = data.status
    alert.feedback_notes = data.notes
    db.commit()
    return {"message": "Feedback submitted"}


@app.post("/api/ml/retrain")
def retrain_model(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually triggers model retraining."""
    from services.ml_service import MLService
    if MLService.train_model(db):
        return {"message": "Model retrained successfully."}
    return JSONResponse(status_code=400, content={"error": "Retraining failed (insufficient data?)"})


@app.post("/api/ml/detect")
def detect_anomalies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger anomaly scan across all users (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.ml_service import MLService
    results = MLService.scan_all_users(db)
    return {"detected": len(results), "details": results}


# ============================================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/api/users")
def get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    """Get all users for admin management."""
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "status": "Enabled" if u.is_active else "Disabled",
            "is_suspicious": u.is_suspicious,
            "created_at": u.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "last_login": u.last_login.strftime("%Y-%m-%d %H:%M:%S") if u.last_login else None,
        }
        for u in users
    ]


@app.get("/admin/users")
def admin_users_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return templates.TemplateResponse(
        "admin_users.html",
        {"request": request, "current_user": current_user, "users": users},
    )


@app.get("/admin/activity")
def admin_activity_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    activities = (
        db.query(UserActivity)
        .order_by(UserActivity.login_time.desc())
        .limit(200)
        .all()
    )
    return templates.TemplateResponse(
        "admin_activity.html",
        {"request": request, "current_user": current_user, "activities": activities},
    )


@app.get("/admin/alerts")
def admin_alerts_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    alerts = db.query(SecurityAlert).order_by(SecurityAlert.timestamp.desc()).limit(200).all()
    return templates.TemplateResponse(
        "admin_alerts.html",
        {"request": request, "current_user": current_user, "alerts": alerts},
    )


@app.get("/api/admin/activity")
def get_admin_activity(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    activities = (
        db.query(UserActivity)
        .order_by(UserActivity.login_time.desc())
        .limit(300)
        .all()
    )
    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "username": a.user.username if a.user else "unknown",
            "ip_address": a.ip_address or "unknown",
            "device_info": a.device_info or "unknown_device",
            "login_time": a.login_time.strftime("%Y-%m-%d %H:%M:%S"),
            "activity_type": a.activity_type,
            "risk_score": round(float(a.risk_score or 0.0), 2),
        }
        for a in activities
    ]


@app.get("/api/admin/alerts")
def get_admin_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    alerts = db.query(SecurityAlert).order_by(SecurityAlert.timestamp.desc()).limit(300).all()
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "username": row.user.username if row.user else f"user-{row.user_id}",
            "alert_type": row.alert_type,
            "description": row.description,
            "severity": row.severity,
            "verdict": row.verdict or "pending",
            "timestamp": row.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for row in alerts
    ]


@app.put("/api/admin/alerts/{alert_id}/verdict")
def update_admin_alert_verdict(
    alert_id: int,
    payload: AlertVerdictPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    verdict = (payload.verdict or "").strip().lower()
    if verdict not in {"safe", "threat", "pending"}:
        raise HTTPException(status_code=400, detail="Verdict must be safe, threat, or pending")
    alert = db.query(SecurityAlert).filter(SecurityAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.verdict = verdict
    db.commit()
    return {"id": alert.id, "verdict": alert.verdict}


@app.get("/api/admin/overview")
def get_admin_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    disabled_users = db.query(User).filter(User.is_active == False).count()
    suspicious_logins = (
        db.query(UserActivity)
        .filter(
            UserActivity.activity_type.in_(
                ["suspicious_multi_ip_login", "new_device_login", "login_failed_disabled_account"]
            ),
            UserActivity.login_time >= datetime.utcnow() - timedelta(hours=24),
        )
        .count()
    )
    return {
        "total_users": total_users,
        "active_users": active_users,
        "disabled_users": disabled_users,
        "suspicious_logins": suspicious_logins,
    }


@app.get("/api/admin/activity-chart")
def get_admin_activity_chart(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    now = datetime.utcnow()
    buckets = []
    for idx in range(5, -1, -1):
        bucket_start = now - timedelta(minutes=(idx + 1) * 5)
        bucket_end = now - timedelta(minutes=idx * 5)
        count = (
            db.query(UserActivity)
            .filter(
                UserActivity.login_time >= bucket_start,
                UserActivity.login_time < bucket_end,
            )
            .count()
        )
        buckets.append(
            {
                "label": bucket_end.strftime("%H:%M"),
                "count": count,
            }
        )
    return buckets


@app.put("/api/users/{user_id}/status")
def update_user_status(
    user_id: int,
    status: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    """Enable or disable a user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    is_active = status.get("is_active")
    if is_active is None:
        raise HTTPException(status_code=400, detail="is_active field required")
    
    user.is_active = bool(is_active)
    user.status = "Enabled" if user.is_active else "Disabled"
    if not user.is_active:
        revoke_user(user.id)
    _record_user_activity(
        db,
        user=user,
        activity_type="account_enabled" if user.is_active else "account_disabled",
        risk_score=float(user.risk_score or 0.0),
    )
    db.commit()
    return {"message": f"User {user.username} {'enabled' if is_active else 'disabled'}"}


@app.post("/admin/disable-user/{user_id}")
def disable_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    user.status = "Disabled"
    user.is_suspicious = True
    revoke_user(user.id)
    _record_user_activity(
        db,
        user=user,
        activity_type="account_disabled",
        request=request,
        risk_score=max(float(user.risk_score or 0.0), 55.0),
    )
    db.commit()
    return {"message": "User disabled", "user_id": user.id}


@app.post("/admin/enable-user/{user_id}")
def enable_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    user.status = "Enabled"
    _record_user_activity(
        db,
        user=user,
        activity_type="account_enabled",
        request=request,
        risk_score=float(user.risk_score or 0.0),
    )
    db.commit()
    return {"message": "User enabled", "user_id": user.id}


# ============================================================================
# SAAS TENANT ADMIN ENDPOINTS
# ============================================================================

@app.post("/api/admin/tenants")
def create_tenant(
    payload: TenantCreatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    existing = db.query(Tenant).filter(func.lower(Tenant.name) == payload.name.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tenant name already exists")

    tenant = Tenant(name=payload.name.strip(), region=payload.region.strip())
    db.add(tenant)
    db.flush()

    sub = TenantSubscription(tenant_id=tenant.id, tier=payload.tier, status="active")
    ml_cfg = TenantMLConfig(tenant_id=tenant.id, retraining_enabled=True)
    db.add(sub)
    db.add(ml_cfg)
    db.commit()
    db.refresh(tenant)

    return {
        "tenant_id": tenant.id,
        "name": tenant.name,
        "region": tenant.region,
        "tier": sub.tier,
        "retraining_enabled": ml_cfg.retraining_enabled,
    }


@app.get("/api/admin/tenants")
def list_tenants(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    tenants = db.query(Tenant).order_by(Tenant.created_at.desc()).all()
    output = []
    for tenant in tenants:
        sub = (
            db.query(TenantSubscription)
            .filter(TenantSubscription.tenant_id == tenant.id)
            .order_by(TenantSubscription.updated_at.desc())
            .first()
        )
        ml_cfg = db.query(TenantMLConfig).filter(TenantMLConfig.tenant_id == tenant.id).first()
        tenant_user_count = db.query(User).filter(User.tenant_id == tenant.id).count()
        tenant_avg_risk = db.query(func.avg(User.risk_score)).filter(User.tenant_id == tenant.id).scalar() or 0.0
        output.append(
            {
                "tenant_id": tenant.id,
                "name": tenant.name,
                "region": tenant.region,
                "is_active": tenant.is_active,
                "tier": sub.tier if sub else "starter",
                "subscription_status": sub.status if sub else "active",
                "retraining_enabled": ml_cfg.retraining_enabled if ml_cfg else True,
                "user_count": tenant_user_count,
                "avg_risk_score": round(float(tenant_avg_risk), 2),
                "created_at": tenant.created_at.isoformat(),
            }
        )
    return output


@app.put("/api/admin/tenants/{tenant_id}/tier")
def update_tenant_tier(
    tenant_id: str,
    payload: TenantTierUpdatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    subscription = (
        db.query(TenantSubscription)
        .filter(TenantSubscription.tenant_id == tenant_id)
        .order_by(TenantSubscription.updated_at.desc())
        .first()
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Tenant subscription not found")
    subscription.tier = payload.tier
    db.commit()
    return {"tenant_id": tenant_id, "tier": subscription.tier}


@app.put("/api/admin/tenants/{tenant_id}/ml-retraining")
def toggle_tenant_ml_retraining(
    tenant_id: str,
    payload: TenantMLTogglePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin")),
):
    cfg = db.query(TenantMLConfig).filter(TenantMLConfig.tenant_id == tenant_id).first()
    if not cfg:
        cfg = TenantMLConfig(tenant_id=tenant_id)
        db.add(cfg)
    cfg.retraining_enabled = payload.retraining_enabled
    db.commit()
    return {"tenant_id": tenant_id, "retraining_enabled": cfg.retraining_enabled}


# ============================================================================
# PASSWORD RESET AND FORGOT PASSWORD ENDPOINTS
# ============================================================================

@app.get("/forgot-password")
async def forgot_password_page(request: Request):
    """
    Display the forgot password page.
    
    Advantages:
    - Secure password recovery mechanism
    - User-friendly interface with clear instructions
    - Prevents account lockouts due to forgotten passwords
    """
    return templates.TemplateResponse("forgot_password.html", {"request": request})


@app.post("/forgot-password")
async def forgot_password(
    email: str = Form(...),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Handle forgot password request.
    
    Advantages:
    - Secure token generation using cryptographic random
    - 15-minute expiry prevents token abuse
    - Email-based verification adds security layer
    """
    user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
    
    if user:
        # Generate secure reset token
        reset_token = generate_password_reset_token()
        expiry = get_password_reset_token_expiry()
        
        # Store token in database
        password_reset = PasswordResetToken(
            user_id=user.id,
            token=reset_token,
            expires_at=expiry,
            used=False
        )
        db.add(password_reset)
        db.commit()
        
        # TODO: Send reset email using SMTP
        # For now, log the token (in production, send via email)
        print(f"Password reset token for {email}: {reset_token}")
        
        return templates.TemplateResponse(
            "forgot_password.html",
            {
                "request": request,
                "success": "If an account exists with this email, you will receive a password reset link shortly."
            }
        )
    
    # Return same message for security (don't reveal if email exists)
    return templates.TemplateResponse(
        "forgot_password.html",
        {
            "request": request,
            "success": "If an account exists with this email, you will receive a password reset link shortly."
        }
    )


@app.get("/reset-password/{token}")
async def reset_password_page(
    token: str,
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Display the reset password page.
    
    Advantages:
    - Token validation ensures only valid resets can proceed
    - Expiry check prevents stale tokens from being used
    - Prevents token reuse through 'used' flag
    """
    from datetime import datetime, timezone
    
    # Find and validate token
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token
    ).first()
    
    valid_token = False
    
    if reset_token:
        # Check if token is valid (not used, not expired)
        if not reset_token.used and reset_token.expires_at > datetime.now(timezone.utc):
            valid_token = True
    
    return templates.TemplateResponse(
        "reset_password.html",
        {
            "request": request,
            "token": token,
            "valid_token": valid_token
        }
    )


@app.post("/reset-password/{token}")
async def reset_password(
    token: str,
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Process password reset.
    
    Advantages:
    - Validates password match before processing
    - Uses bcrypt for secure password hashing
    - Marks token as used to prevent reuse
    - Updates user account with new password
    """
    from datetime import datetime, timezone
    
    # Validate passwords match
    if password != confirm_password:
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "token": token,
                "valid_token": False,
                "error": "Passwords do not match"
            }
        )
    
    # Validate password strength
    if len(password) < 8:
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "token": token,
                "valid_token": False,
                "error": "Password must be at least 8 characters"
            }
        )
    
    # Find and validate token
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token
    ).first()
    
    if not reset_token:
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "token": token,
                "valid_token": False
            }
        )
    
    # Check if token is valid
    if reset_token.used or reset_token.expires_at < datetime.now(timezone.utc):
        return templates.TemplateResponse(
            "reset_password.html",
            {
                "request": request,
                "token": token,
                "valid_token": False
            }
        )
    
    # Update user password
    user = reset_token.user
    user.hashed_password = get_password_hash(password)
    reset_token.used = True
    
    db.commit()
    
    return RedirectResponse(
        url="/login?success=Password reset successfully. Please login with your new password.",
        status_code=status.HTTP_302_FOUND
    )


# ============================================================================
# OAUTH AUTHENTICATION ENDPOINTS (Google, GitHub, Microsoft)
# ============================================================================

@app.get("/auth/google/login")
async def auth_google(request: Request):
    """
    Initiates Google OAuth flow.

    This handler redirects the user to Google's authorization endpoint
    using Authlib. The `state` parameter is automatically generated and
    validated by the library to prevent CSRF. On return, Google will call
    our `/auth/google/callback` endpoint.
    """
    if oauth is None:
        return RedirectResponse(
            url="/login?error=Google login is not configured",
            status_code=status.HTTP_302_FOUND,
        )
    redirect_uri = request.url_for('auth_google_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback")
async def auth_google_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle Google OAuth callback.

    On success we receive a token from Google which includes userinfo.
    We then:
      * extract email and google_id
      * lookup user by email
      * create user if none exists
      * issue JWT and set cookie
    """
    if oauth is None:
        return RedirectResponse(
            url="/login?error=Google login is not configured",
            status_code=status.HTTP_302_FOUND,
        )
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        error_msg = f"Invalid token: {error.description}"
        return RedirectResponse(url=f"/login?error={error_msg}")

    user_info = token.get('userinfo')
    if not user_info:
        return RedirectResponse(url='/login?error=Failed to get user info')

    email = user_info.get('email')
    google_id = user_info.get('sub')

    # check for existing user
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            username=email.split('@')[0],
            email=email,
            google_id=google_id,
            is_active=True,
            status="Enabled",
            email_verified=True,
            role='user'
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if not user.google_id:
            user.google_id = google_id
            db.commit()

    access_token = create_access_token(data={'sub': user.email})
    response = RedirectResponse(url='/dashboard')
    _set_auth_cookie(response, access_token)
    return response


@app.get("/auth/github/login")
async def auth_github(request: Request):
    """
    Initiates GitHub OAuth flow. Redirects user to GitHub consent screen.
    """
    if oauth is None:
        return RedirectResponse(
            url="/login?error=GitHub login is not configured",
            status_code=status.HTTP_302_FOUND,
        )
    redirect_uri = request.url_for('auth_github_callback')
    return await oauth.github.authorize_redirect(request, redirect_uri)


@app.get("/auth/github/callback")
async def auth_github_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle GitHub OAuth callback. Creates or updates a user then issues JWT.
    """
    if oauth is None:
        return RedirectResponse(
            url="/login?error=GitHub login is not configured",
            status_code=status.HTTP_302_FOUND,
        )
    try:
        token = await oauth.github.authorize_access_token(request)
    except OAuthError as error:
        return RedirectResponse(url=f"/login?error=GitHub auth failed: {error.description}")

    profile = await oauth.github.get('user', token=token)
    data = profile.json()
    github_id = str(data.get('id'))
    email = data.get('email')
    # GitHub may not return email in user object, fetch separately
    if not email:
        emails_resp = await oauth.github.get('user/emails', token=token)
        for e in emails_resp.json():
            if e.get('primary') and e.get('verified'):
                email = e.get('email')
                break
    if not email:
        return RedirectResponse(url='/login?error=GitHub did not return email')

    user = db.query(User).filter(User.github_id == github_id).first()
    if not user:
        existing = db.query(User).filter(func.lower(User.email) == email.lower()).first()
        if existing:
            existing.github_id = github_id
            db.commit()
            user = existing
        else:
            user = User(
                username=email.split('@')[0],
                email=email.lower(),
                hashed_password=None,
                role='user',
                github_id=github_id,
                tenant_id='default',
                status="Enabled",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
    access_token = create_access_token(data={"sub": user.email})
    response = RedirectResponse(url='/dashboard')
    _set_auth_cookie(response, access_token)
    return response


@app.get("/auth/microsoft")
async def auth_microsoft(request: Request):
    """
    Initiates Microsoft OAuth flow.
    
    Advantages:
    - Enterprise-friendly authentication
    - Azure AD integration support
    - Corporate account compatibility
    """
    return RedirectResponse(url="/login?error=Microsoft OAuth not yet configured", status_code=status.HTTP_302_FOUND)



@app.get("/{path:path}")
async def serve_spa(request: Request, path: str):
    if path.startswith("api/") or path.startswith("static/"):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return templates.TemplateResponse("index.html", {"request": request})
