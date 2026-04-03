from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, WebSocket, WebSocketDisconnect, File, UploadFile
from config import Config

from fastapi.responses import RedirectResponse, JSONResponse
import shutil
import os
import uuid
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta

from sqlalchemy import func
from app.database import get_db
from app.models import User, Activity, SecurityAlert, Alert, PasswordResetToken, Inquiry, Location

from app.auth import (
    verify_password,
    hash_password,
    create_access_token,
    create_refresh_token,
    TOKEN_COOKIE_NAME,
    generate_password_reset_token,
    get_password_reset_token_expiry
)

from app.security import get_current_user, get_current_admin_user
from app.schemas import ProfileUpdate

from app.otp_service import (
    generate_otp,
    send_email_otp,
    send_email,
    otp_expiry,
    OTP_MAX_ATTEMPTS,
    OTP_RATE_LIMIT_MAX,
    OTP_RATE_LIMIT_WINDOW_MINUTES
)

import re
from app.services.activity_service import ActivityService
from app.services.risk_engine import RiskEngine
from app.services.alert_service import AlertService
from app.anomaly_detection import AnomalyDetector
import logging

logger = logging.getLogger("ueba")

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

from app.websocket_manager import manager

@router.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We just need to keep the connection open, clients don't send data here
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@router.websocket("/ws/location")
async def websocket_location(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ---------------- OTP Helper ----------------

def _issue_otp(user: User, db: Session) -> str:
    now = datetime.utcnow()

    if user.otp_sent_at and user.otp_sent_at > now - timedelta(minutes=OTP_RATE_LIMIT_WINDOW_MINUTES):
        if (user.otp_request_count or 0) >= OTP_RATE_LIMIT_MAX:
            raise HTTPException(status_code=429, detail="OTP rate limit exceeded")
    else:
        user.otp_request_count = 0

    otp = generate_otp()

    user.otp_code = otp          # matches DB column: otp_code
    user.otp_expiry = otp_expiry()
    user.otp_attempts = 0
    user.otp_request_count = (user.otp_request_count or 0) + 1
    user.otp_sent_at = now

    db.commit()

    return otp


# ---------------- Pages ----------------

@router.get("/")
async def home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "user": current_user}
    )


@router.get("/login")
async def login_page(request: Request, current_user: User = Depends(get_current_user)):
    if current_user:
        return RedirectResponse("/dashboard")
    success = request.query_params.get("success", "")
    return templates.TemplateResponse("login.html", {"request": request, "success": success, "user": current_user})


@router.get("/signup")
async def signup_page(request: Request, current_user: User = Depends(get_current_user)):
    if current_user:
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse("signup.html", {"request": request, "user": current_user})

@router.get("/admin/login")
async def admin_login_page(request: Request, current_user: User = Depends(get_current_user)):
    if current_user and current_user.role == "admin":
        return RedirectResponse("/admin-dashboard")
    return templates.TemplateResponse("admin_login.html", {"request": request, "user": current_user})


@router.get("/dashboard")
async def dashboard(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse("/login")

    if current_user.role == "admin":
        users = db.query(User).all()
    else:
        users = [current_user]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": current_user,
            "users": users,
            "google_maps_api_key": Config.GOOGLE_MAPS_API_KEY
        }
    )


@router.get("/profile")
@router.get("/profile/{user_id}")
async def profile_page(
    request: Request,
    user_id: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse("/login")

    target_user = current_user
    if user_id:
        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            raise HTTPException(status_code=404, detail="Analyst not found")

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request, 
            "user": target_user, 
            "current_user": current_user,
            "is_own_profile": target_user.id == current_user.id
        }
    )



@router.get("/api/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    if not current_user:
        return {"username": None, "email": None, "role": "guest"}
    return {
        "username": current_user.username or "Unknown",
        "email": current_user.email or "",
        "role": current_user.role or "user"
    }

@router.post("/api/user/profile")
async def update_profile(
    update_data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if update_data.username is not None and update_data.username != current_user.username:
        # Check if username is already taken
        existing_user = db.query(User).filter(User.username == update_data.username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already taken")
        current_user.username = update_data.username

    if update_data.phone is not None:
        current_user.phone = update_data.phone

    try:
        db.commit()
        db.refresh(current_user)
        logger.info(f"Profile updated for user: {current_user.email}")
        return {"status": "success", "message": "Profile updated"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating profile for {current_user.email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal database error during profile sync")


@router.post("/api/user/upload-profile-pic")
async def upload_profile_pic(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Validate file type
    if file.content_type not in ["image/jpeg", "image/png", "image/gif"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Only JPG, PNG, and GIF allowed.")

    # Create directory if it doesn't exist
    upload_dir = "app/static/uploads/profile_pics"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)

    # Generate unique filename
    file_ext = os.path.splitext(file.filename)[1]
    filename = f"{current_user.id}_{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(upload_dir, filename)

    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Error saving profile pic: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save image")

    # Update user record
    # Delete old file if exists
    if current_user.profile_pic:
        old_path = os.path.join("app", current_user.profile_pic.lstrip("/"))
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception as e:
                logger.warning(f"Failed to delete old profile pic {old_path}: {str(e)}")

    current_user.profile_pic = f"/static/uploads/profile_pics/{filename}"
    db.commit()

    return {"status": "success", "profile_pic": current_user.profile_pic}




# ---------------- Login ----------------

@router.post("/login")
async def login(
        request: Request,
        email: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()

    if not user:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JSONResponse({"status": "error", "error": "Invalid email or password"}, status_code=401)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password"}
        )

    # Check if account is blocked by admin
    if not user.is_active:
        logger.warning(f"Login attempted on blocked account: {email}")
        error_msg = "Account blocked by admin"
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JSONResponse({"status": "error", "error": error_msg}, status_code=403)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": error_msg}
        )

    # Check if account is locked
    if user.locked_until and user.locked_until > datetime.utcnow():
        logger.warning(f"Login attempted on locked account: {email}")
        error_msg = f"Account locked. Try again after {user.locked_until.strftime('%H:%M:%S UTC')}"
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JSONResponse({"status": "error", "error": error_msg}, status_code=403)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": error_msg}
        )

    if not verify_password(password, user.hashed_password):
        # Update failed attempts
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=15)
            logger.warning(f"Account locked due to consecutive failures: {email}")
        
        # Log failed activity
        activity, _ = await ActivityService.log_activity(db, request, user, status="failed")
        db.add(activity)
        db.commit()
        
        logger.info(f"Failed login attempt for user: {email} from IP: {activity.ip_address}")
        
        # Broadcast Failure Event
        import asyncio
        asyncio.create_task(manager.broadcast({
            "type": "login",
            "username": user.username,
            "ip_address": activity.ip_address,
            "browser": activity.browser,
            "city": activity.city,
            "country": activity.country,
            "lat": activity.latitude,
            "lon": activity.longitude,
            "risk_score": 0,
            "is_threat": True, # Failures are treated as bad activity
            "status": "failed"
        }))
        
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JSONResponse({"status": "error", "error": "Invalid email or password"}, status_code=401)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password"}
        )

    # Success
    user.failed_login_attempts = 0
    user.locked_until = None
    
    # Log successful activity
    activity, activity_data = await ActivityService.log_activity(db, request, user, status="success")
    
    # Update User record with last login info
    user.last_login = datetime.utcnow()
    user.last_login_ip = activity.ip_address
    
    # Calculate Risk Score
    risk_score, risk_reasons = RiskEngine.calculate_risk(db, user, activity_data)
    activity.risk_score = risk_score
    user.risk_score = risk_score
    user.last_risk_calculation = datetime.utcnow()
    db.add(activity)
    
    reasons_str = " | ".join(risk_reasons) if risk_reasons else "Normal behavior"
    logger.info(f"Successful login for user: {email} | IP: {activity.ip_address} | Risk Score: {risk_score} | Reasons: {reasons_str}")
    
    # Trigger Alerts if Risk > 50
    alert = AlertService.generate_risk_alert(
        db, user.id, risk_score, activity.ip_address,
        reason=reasons_str
    )
    if alert:
        logger.warning(f"Security Alert generated for user {email}: {alert.description}")
        
    # Run ML Anomaly Detection
    detector = AnomalyDetector()
    ml_alert = detector.train_and_detect(db, user.id)
    if ml_alert:
        logger.warning(f"ML Anomaly Alert generated for user {email}: {ml_alert.feedback_notes}")
    
    db.commit()

    # Broadcast Success Event
    is_threat = risk_score >= 50
    import asyncio
    asyncio.create_task(manager.broadcast({
        "type": "login",
        "username": user.username,
        "ip_address": activity.ip_address,
        "browser": activity.browser,
        "city": activity.city,
        "country": activity.country,
        "lat": activity.latitude,
        "lon": activity.longitude,
        "risk_score": risk_score,
        "is_threat": is_threat,
        "status": "success"
    }))
    
    if alert:
        asyncio.create_task(manager.broadcast({
            "type": "alert",
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "description": alert.description,
            "ip_address": alert.ip_address
        }))
    if ml_alert:
        asyncio.create_task(manager.broadcast({
            "type": "alert",
            "alert_type": "ML Anomaly",
            "severity": ml_alert.risk_level or "High",
            "description": ml_alert.feedback_notes,
            "ip_address": activity.ip_address
        }))

    access_token = create_access_token(data={"sub": user.email})

    # Prepare response
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", ""):
        response = JSONResponse({
            "status": "success",
            "user_id": user.id,
            "redirect": "/dashboard"
        })
    else:
        response = RedirectResponse("/dashboard", status_code=303)

    # Set authentication cookie for both JSON and Redirect responses
    response.set_cookie(
        key=TOKEN_COOKIE_NAME,
        value=access_token,
        httponly=True,
        max_age=3600
    )
    return response

@router.post("/api/activity/location")
async def log_location(
    request: Request,
    db: Session = Depends(get_db)
):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        lat = data.get("latitude")
        lon = data.get("longitude")
        
        if not user_id or lat is None or lon is None:
            return JSONResponse({"status": "error", "message": "Invalid GPS payload"}, status_code=400)
            
        # Update the most recent success activity
        activity = db.query(Activity).filter(
            Activity.user_id == user_id,
            Activity.status == 'success'
        ).order_by(Activity.login_time.desc()).first()
        
        if activity:
            activity.latitude = float(lat)
            activity.longitude = float(lon)
            
            # RE-RESOLVE city name from coordinates (Reverse Geocoding)
            ip = ActivityService.get_client_ip(request)
            geo = await ActivityService.get_geolocation(ip, lat=float(lat), lon=float(lon))
            
            if geo.get("status") == "success":
                activity.city = geo.get("city")
                activity.country = geo.get("country")
                activity.location = f"{activity.city}, {activity.country}"
            
            db.commit()
            return {"status": "success", "resolved_city": activity.city}
            
        return JSONResponse({"status": "error", "message": "No recent activity"}, status_code=404)
    except Exception as e:
        logger.error(f"GPS log error: {str(e)}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@router.post("/api/location")
async def save_location(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        return JSONResponse({"status": "error", "message": "Not authenticated"}, status_code=401)
        
    try:
        # Support both JSON and Form data for flexibility
        if "application/json" in request.headers.get("Content-Type", ""):
            data = await request.json()
            lat = data.get("lat") or data.get("latitude")
            lon = data.get("lon") or data.get("longitude")
        else:
            form_data = await request.form()
            lat = form_data.get("lat") or form_data.get("latitude")
            lon = form_data.get("lon") or form_data.get("longitude")
        
        if lat is None or lon is None:
            return JSONResponse({"status": "error", "message": "Invalid coordinates"}, status_code=400)
            
        lat = float(lat)
        lon = float(lon)

        # 1. Save to Location table (Live Tracking)
        location_entry = Location(
            user_id=current_user.id,
            latitude=lat,
            longitude=lon,
            timestamp=datetime.utcnow()
        )
        db.add(location_entry)
        
        # 2. Update the most recent Activity record (Last Known Position)
        # Optimization: We skip reverse geocoding (nominatim) here because it's too slow for live tracking.
        # We only update the coordinates.
        activity = db.query(Activity).filter(
            Activity.user_id == current_user.id,
            Activity.status == 'success'
        ).order_by(Activity.login_time.desc()).first()
        
        if activity:
            # If this is the first real GPS fix, or the location is currently generic, resolve the city
            needs_resolution = (not activity.latitude or not activity.longitude or 
                               activity.city in ["Internal Network", "Unknown", "Internal"])
            
            activity.latitude = lat
            activity.longitude = lon
            
            if needs_resolution:
                ip = ActivityService.get_client_ip(request)
                geo = await ActivityService.get_geolocation(ip, lat=lat, lon=lon)
                if geo.get("status") == "success":
                    activity.city = geo.get("city")
                    activity.country = geo.get("country")
                    activity.location = f"{activity.city}, {activity.country}"
                    logger.info(f"Resolved city {activity.city} from GPS for user {current_user.username}")
        
        # 3. Broadcast via WebSocket (Using harmonized field names: lat, lon)
        import asyncio
        asyncio.create_task(manager.broadcast({
            "type": "location_update",
            "user_id": current_user.id,
            "username": current_user.username,
            "lat": lat,
            "lon": lon,
            "timestamp": location_entry.timestamp.isoformat() + "Z"
        }))
        
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error saving live location: {str(e)}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)



# ---------------- Signup ----------------

def is_strong_password(password: str) -> bool:
    if len(password) < 8: return False
    if not re.search(r"\d", password): return False
    if not re.search(r"[A-Za-z]", password): return False
    if not re.search(r"[@$!%*#?&]", password): return False
    return True

@router.post("/signup")
async def signup(
        request: Request,
        username: str = Form(...),
        email: str = Form(...),
        phone: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
):
    if not is_strong_password(password):
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Password must be at least 8 chars, contain a number, an alphabet, and a special character."}
        )
    existing = db.query(User).filter(User.email == email).first()

    if existing:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Email already exists"}
        )

    user = User(
        username=username,
        email=email,
        phone=phone,
        hashed_password=hash_password(password),
        status="active",
        is_verified=False,
        created_at=datetime.utcnow()
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Email already exists"}
        )

    otp = _issue_otp(user, db)
    send_email_otp(user.email, otp)

    request.session["otp_identifier"] = user.email
    request.session["otp_purpose"] = "signup"

    return RedirectResponse("/verify-otp", status_code=303)


# ---------------- Logout ----------------

@router.get("/logout")
def logout():
    response = RedirectResponse("/login")
    response.delete_cookie(TOKEN_COOKIE_NAME)
    return response


# ---------------- Forgot Password ----------------

@router.get("/forgot-password")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})


import secrets

@router.post("/forgot-password")
def forgot_password(
        request: Request,
        email: str = Form(...),
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()

    # If user doesn't exist, create a temporary/inactive one so we can track the OTP
    if not user:
        # Generate a safe temporary username
        temp_username = f"temp_{email.split('@')[0]}_{secrets.token_hex(4)}"
        user = User(
            username=temp_username,
            email=email,
            # Generate a random impossible hashed password for now
            hashed_password=hash_password(secrets.token_hex(16)),
            status="inactive",
            is_verified=False
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except Exception as e:
            db.rollback()
            return templates.TemplateResponse(
                "forgot_password.html",
                {"request": request, "error": "Could not process that email address."}
            )

    try:
        otp = _issue_otp(user, db)
    except HTTPException as exc:
        return templates.TemplateResponse(
            "forgot_password.html",
            {"request": request, "error": exc.detail}
        )

    send_email_otp(user.email, otp)

    request.session["otp_identifier"] = user.email
    request.session["otp_purpose"] = "reset"

    return RedirectResponse("/verify-otp", status_code=303)


# ---------------- Verify OTP ----------------

@router.get("/verify-otp")
async def verify_otp_page(request: Request):
    identifier = request.session.get("otp_identifier", "")
    purpose = request.session.get("otp_purpose", "reset")
    return templates.TemplateResponse(
        "verify_otp.html",
        {"request": request, "identifier": identifier, "purpose": purpose}
    )


@router.post("/verify-otp")
def verify_otp(
        request: Request,
        identifier: str = Form(...),
        otp: str = Form(...),
        purpose: str = Form("reset"),
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == identifier).first()

    if not user:
        return templates.TemplateResponse(
            "verify_otp.html",
            {"request": request, "identifier": identifier, "purpose": purpose,
             "error": "User not found. Please start over."}
        )

    now = datetime.utcnow()

    # Check OTP expiry
    if not user.otp_expiry or now > user.otp_expiry:
        return templates.TemplateResponse(
            "verify_otp.html",
            {"request": request, "identifier": identifier, "purpose": purpose,
             "error": "OTP has expired. Please request a new one."}
        )

    # Check too many attempts
    if (user.otp_attempts or 0) >= OTP_MAX_ATTEMPTS:
        return templates.TemplateResponse(
            "verify_otp.html",
            {"request": request, "identifier": identifier, "purpose": purpose,
             "error": "Too many failed attempts. Please request a new OTP."}
        )

    # Verify OTP value
    if user.otp_code != otp.strip():
        user.otp_attempts = (user.otp_attempts or 0) + 1
        db.commit()
        remaining = OTP_MAX_ATTEMPTS - user.otp_attempts
        return templates.TemplateResponse(
            "verify_otp.html",
            {"request": request, "identifier": identifier, "purpose": purpose,
             "error": f"Invalid OTP. {remaining} attempt(s) remaining."}
        )

    # OTP is valid — clear it
    user.otp_code = None
    user.otp_expiry = None
    user.otp_attempts = 0
    db.commit()

    if purpose == "reset":
        # Create a one-time password-reset token and redirect to reset page
        reset_token = generate_password_reset_token()
        token_record = PasswordResetToken(
            user_id=user.id,
            token=reset_token,
            expires_at=get_password_reset_token_expiry(),
            used=False
        )
        db.add(token_record)
        db.commit()

        request.session.pop("otp_identifier", None)
        request.session.pop("otp_purpose", None)

        return RedirectResponse(f"/reset-password/{reset_token}", status_code=303)

    # purpose == "signup" — mark verified and log in
    user.is_verified = True
    db.commit()

    request.session.pop("otp_identifier", None)
    request.session.pop("otp_purpose", None)

    access_token = create_access_token(data={"sub": user.email})
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(
        key=TOKEN_COOKIE_NAME,
        value=access_token,
        httponly=True,
        max_age=1800
    )
    return response


# ---------------- Reset Password ----------------

@router.get("/reset-password/{token}")
async def reset_password_page(token: str, request: Request, db: Session = Depends(get_db)):
    now = datetime.utcnow()
    token_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token,
        PasswordResetToken.used == False,
        PasswordResetToken.expires_at > now
    ).first()

    valid = token_record is not None
    return templates.TemplateResponse(
        "reset_password.html",
        {"request": request, "token": token, "valid_token": valid}
    )


@router.post("/reset-password/{token}")
def reset_password(
        token: str,
        request: Request,
        password: str = Form(...),
        confirm_password: str = Form(...),
        db: Session = Depends(get_db)
):
    now = datetime.utcnow()
    token_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == token,
        PasswordResetToken.used == False,
        PasswordResetToken.expires_at > now
    ).first()

    if not token_record:
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "token": token, "valid_token": False}
        )

    if password != confirm_password:
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "token": token, "valid_token": True,
             "error": "Passwords do not match."}
        )

    if not is_strong_password(password):
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "token": token, "valid_token": True,
             "error": "Password must be at least 8 chars, contain a number, a letter, and a special character."}
        )

    user = token_record.user
    user.hashed_password = hash_password(password)
    token_record.used = True
    db.commit()

    return RedirectResponse(
        "/login?success=Password+reset+successfully.+Please+log+in.",
        status_code=303
    )


# ---------------- Resend OTP (JSON endpoint for verify_otp.html) ----------------

@router.post("/send-otp")
async def send_otp(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    identifier = body.get("identifier", "")
    purpose = body.get("purpose", "reset")

    user = db.query(User).filter(User.email == identifier).first()
    if not user:
        return JSONResponse({"ok": False, "detail": "User not found"}, status_code=404)

    try:
        otp = _issue_otp(user, db)
    except HTTPException as exc:
        return JSONResponse({"ok": False, "detail": exc.detail}, status_code=exc.status_code)

    send_email_otp(user.email, otp)
    return JSONResponse({"ok": True})


# ---------------- Dashboard APIs ----------------

@router.post("/enable-user/{user_id}")
def enable_user(
        user_id: int,
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse("/login", status_code=303)

    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.status = 'active'
        db.commit()

    return RedirectResponse("/dashboard", status_code=303)


@router.post("/disable-user/{user_id}")
def disable_user(
        user_id: int,
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse("/login", status_code=303)

    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.status = 'disabled'
        db.commit()

    return RedirectResponse("/dashboard", status_code=303)


@router.get("/api/dashboard/stats")
async def dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Base queries
    user_query = db.query(User)
    activity_query = db.query(Activity.user_id)
    alert_query = db.query(SecurityAlert)
    anomaly_query = db.query(Alert)
    
    # Filter by user if not admin
    if current_user.role != "admin":
        user_query = user_query.filter(User.id == current_user.id)
        activity_query = activity_query.filter(Activity.user_id == current_user.id)
        alert_query = alert_query.filter(SecurityAlert.user_id == current_user.id)
        # Anomaly table 'Alert' needs a user_id or similar. Let's check its schema.
        # Assuming Alert has user_id
        try:
            anomaly_query = anomaly_query.filter(Alert.user_id == current_user.id)
        except:
            pass # Fallback if Alert schema is different

    total_users = user_query.count()

    from datetime import datetime, timedelta
    since = datetime.utcnow() - timedelta(hours=24)
    active_users = activity_query.filter(
        Activity.login_time >= since,
        Activity.status == 'success'
    ).distinct().count()

    security_alerts = alert_query.count()
    anomalies = anomaly_query.count()

    return {
        "total_users": total_users,
        "active_users": active_users,
        "security_alerts": security_alerts,
        "detected_anomalies": anomalies
    }

# ---------------- Contact / Inquiry ----------------

@router.post("/api/contact")
async def contact_inquiry(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        data = await request.json()
        name = data.get("name")
        email = data.get("email")
        subject = data.get("subject")
        message = data.get("message")

        if not all([name, email, subject, message]):
            return JSONResponse({"status": "error", "message": "All fields are required"}, status_code=400)

        # 1. Create Inquiry (for archival/contact purposes)
        inquiry = Inquiry(
            sender_name=name,
            sender_email=email,
            subject=subject,
            message=message
        )
        db.add(inquiry)
        
        # 2. Create SecurityAlert (as requested, connect to backend intelligence)
        # Type: "Intelligence Report", Severity: "Medium" (High if subject contains keywords)
        severity = "High" if any(kw in subject.lower() for kw in ["breach", "threat", "attack", "critical"]) else "Medium"
        
        alert = SecurityAlert(
            user_id=current_user.id if current_user else None,
            alert_type="Intelligence Report",
            severity=severity,
            description=f"External intelligence transmitted: {subject}. Report from {name} ({email}). Msg: {message[:100]}...",
            ip_address=request.client.host if request.client else "Unknown",
            timestamp=datetime.utcnow()
        )
        db.add(alert)
        db.commit()

        # 3. Notify administrator via Email
        admin_email = os.getenv("SMTP_FROM")
        report_content = (
            f"New Platform Intelligence Report Received:\n\n"
            f"From: {name} ({email})\n"
            f"Subject: {subject}\n"
            f"Message:\n{message}\n\n"
            f"UEBA Intelligence System - Alert Generated"
        )
        send_email(admin_email, f"ALERT: Intelligence Received - {subject}", report_content)

        # 4. Broadcast to Live Dashboard via WebSocket
        import asyncio
        asyncio.create_task(manager.broadcast({
            "type": "alert",
            "alert_type": "Intelligence Report",
            "severity": severity,
            "description": f"New report from {name}: {subject}",
            "ip_address": alert.ip_address or "Unknown"
        }))

        logger.info(f"Intelligence report processed for: {email}")
        return {
            "status": "success", 
            "message": "Intelligence transmitted successfully. Our backend core is processing the data.",
            "alert_id": alert.id
        }
    except Exception as e:
        logger.error(f"Intelligence processing error: {str(e)}")
        return JSONResponse({"status": "error", "message": "Failed to process intelligence"}, status_code=500)


# ---------------- Activity Chart ----------------

@router.get("/api/dashboard/activity")
async def activity_chart(
        db: Session = Depends(get_db)
):
    labels = []
    success_counts = []
    failed_counts = []
    anomaly_counts = []

    for i in range(6, -1, -1):
        date = datetime.now() - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        labels.append(date.strftime("%a"))
        
        # Successful logins
        s_count = db.query(Activity).filter(
            Activity.login_time.contains(date_str),
            Activity.status == 'success'
        ).count()
        success_counts.append(s_count)
        
        # Failed logins
        f_count = db.query(Activity).filter(
            Activity.login_time.contains(date_str),
            Activity.status == 'failed'
        ).count()
        failed_counts.append(f_count)
        
        # Anomalies
        a_count = db.query(Alert).filter(
            Alert.detected_at.contains(date_str)
        ).count()
        anomaly_counts.append(a_count)

    return {
        "labels": labels,
        "success": success_counts,
        "failed": failed_counts,
        "anomalies": anomaly_counts,
        "values": success_counts # For backward compatibility with line chart
    }

# ---------------- Risk Distribution ----------------

@router.get("/api/dashboard/risk-distribution")
async def risk_distribution(db: Session = Depends(get_db)):
    low = db.query(User).filter(User.risk_score < 30).count()
    med = db.query(User).filter(User.risk_score >= 30, User.risk_score < 60).count()
    high = db.query(User).filter(User.risk_score >= 60, User.risk_score <= 80).count()
    critical = db.query(User).filter(User.risk_score > 80).count()
    
    return {
        "Low": low,
        "Medium": med,
        "High": high,
        "Critical": critical
    }

# ---------------- Alert Severity ----------------

@router.get("/api/dashboard/alert-severity")
async def alert_severity(db: Session = Depends(get_db)):
    # Assuming severity is stored as 'Low', 'Medium', 'High', 'Critical' in SecurityAlert
    low = db.query(SecurityAlert).filter(SecurityAlert.severity == 'Low').count()
    med = db.query(SecurityAlert).filter(SecurityAlert.severity == 'Medium').count()
    high = db.query(SecurityAlert).filter(SecurityAlert.severity == 'High').count()
    critical = db.query(SecurityAlert).filter(SecurityAlert.severity == 'Critical').count()

    return {
        "Low": low,
        "Medium": med,
        "High": high,
        "Critical": critical
    }

# ---------------- Recent Logic Activity ----------------

@router.get("/api/dashboard/recent-login-activity")
async def recent_login_activity(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Activity)
    
    # Filter by user if not admin
    if current_user.role != "admin":
        query = query.filter(Activity.user_id == current_user.id)
        
    activities = query.order_by(Activity.login_time.desc()).limit(10).all()
    results = []
    for act in activities:
        results.append({
            "username": act.user.username if act.user else "Unknown",
            "login_time": (act.login_time.isoformat() + "Z") if act.login_time else None,
            "ip_address": act.ip_address,
            "browser": act.browser,
            "device": act.device,
            "city": act.city,
            "country": act.country,
            "latitude": act.latitude,
            "longitude": act.longitude,
            "risk_score": act.risk_score
        })
    return results

# ---------------- Security Alerts ----------------

@router.get("/api/dashboard/security-alerts")
async def recent_security_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(SecurityAlert)
    
    # Filter by user if not admin
    if current_user.role != "admin":
        query = query.filter(SecurityAlert.user_id == current_user.id)
        
    alerts = query.order_by(SecurityAlert.timestamp.desc()).limit(10).all()
    results = []
    for alt in alerts:
        results.append({
            "alert_type": alt.alert_type,
            "severity": alt.severity,
            "description": alt.description,
            "timestamp": (alt.timestamp.isoformat() + "Z") if alt.timestamp else None,
            "ip_address": alt.ip_address
        })
    return results


# ---------------- Admin APIs ----------------

@router.get("/admin-dashboard")
@router.get("/admin/dashboard")
async def admin_dashboard(
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    return templates.TemplateResponse(
        "admin_dashboard.html",
        {"request": request, "user": current_user, "google_maps_api_key": Config.GOOGLE_MAPS_API_KEY}
    )
@router.get("/admin/users")
async def admin_users_page(
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    users = db.query(User).all()
    return templates.TemplateResponse(
        "admin_users.html",
        {"request": request, "user": current_user, "users": users}
    )

@router.get("/admin/activity")
async def admin_activity_page(
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    activities = db.query(Activity).order_by(Activity.login_time.desc()).limit(100).all()
    return templates.TemplateResponse(
        "admin_activity.html",
        {"request": request, "user": current_user, "activities": activities}
    )

@router.get("/admin/alerts")
async def admin_alerts_page(
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    alerts = db.query(SecurityAlert).order_by(SecurityAlert.timestamp.desc()).limit(100).all()
    return templates.TemplateResponse(
        "admin_alerts.html",
        {"request": request, "user": current_user, "alerts": alerts}
    )

@router.get("/api/admin/users")
async def admin_get_users(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    users = db.query(User).all()
    return [{
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "role": u.role,
        "risk_score": u.risk_score,
        "is_active": u.is_active,
        "profile_pic": u.profile_pic
    } for u in users]

@router.get("/api/admin/high-risk-users")
async def admin_get_high_risk_users(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    users = db.query(User).filter(User.risk_score > 50).all()
    return [{
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "role": u.role,
        "risk_score": u.risk_score,
        "is_active": u.is_active,
        "profile_pic": u.profile_pic
    } for u in users]

@router.put("/api/admin/users/{user_id}/block")
async def admin_block_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    user.status = "disabled" # Legacy field support
    db.commit()
    return {"message": "User blocked successfully"}

@router.put("/api/admin/users/{user_id}/unblock")
async def admin_unblock_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    user.status = "active" # Legacy field support
    db.commit()
    return {"message": "User unblocked successfully"}

@router.get("/api/admin/alerts")
async def admin_get_alerts(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    alerts = db.query(SecurityAlert).order_by(SecurityAlert.timestamp.desc()).all()
    return [{
        "id": a.id,
        "user": a.user.username if a.user else "Unknown",
        "alert_type": a.alert_type,
        "severity": a.severity,
        "description": a.description,
        "timestamp": (a.timestamp.isoformat() + "Z") if a.timestamp else None
    } for a in alerts]

@router.delete("/api/admin/users/{user_id}")
async def admin_delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

@router.post("/admin/login")
async def admin_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()

    if not user:
        return JSONResponse({"status": "error", "error": "Invalid administrative credentials"}, status_code=401)

    if user.role != "admin":
        logger.warning(f"Unauthorized admin login attempt: {email}")
        return JSONResponse({"status": "error", "error": "Administrative access required"}, status_code=403)

    if not verify_password(password, user.hashed_password):
        return JSONResponse({"status": "error", "error": "Invalid administrative credentials"}, status_code=401)

    # Success - create token
    access_token = create_access_token(data={"sub": user.email})
    response = JSONResponse({
        "status": "success",
        "redirect": "/admin-dashboard"
    })
    response.set_cookie(
        key=TOKEN_COOKIE_NAME,
        value=access_token,
        httponly=True,
        max_age=3600
    )
    return response

@router.get("/api/admin/activities")
async def admin_get_all_activities(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    activities = db.query(Activity).order_by(Activity.login_time.desc()).limit(100).all()
    return [{
        "id": act.id,
        "username": act.user.username if act.user else "Unknown",
        "profile_pic": act.user.profile_pic if act.user else None,
        "login_time": act.login_time.isoformat() if act.login_time else None,
        "ip_address": act.ip_address,
        "browser": act.browser,
        "location": act.location or f"{act.city}, {act.country}" if (act.city and act.country) else "Unknown",
        "risk_score": act.risk_score,
        "status": act.status
    } for act in activities]

@router.delete("/api/admin/activities")
async def admin_clear_activities(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Deletes all records from the activities table.
    """
    try:
        db.query(Activity).delete()
        db.commit()
        logger.info(f"Admin {current_user.email} cleared all activity logs.")
        return {"status": "success", "message": "All login activities have been cleared."}
    except Exception as e:
        db.rollback()
        logger.error(f"Error clearing activities: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to clear activity logs")

@router.get("/api/admin/active-users")
async def admin_get_active_users(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    # Users active in the last 15 minutes
    fifteen_mins_ago = datetime.utcnow() - timedelta(minutes=15)
    active_users = db.query(User).filter(User.last_activity >= fifteen_mins_ago).all()
    
    return [{
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "last_activity": (u.last_activity.isoformat() + "Z") if u.last_activity else None,
        "risk_score": u.risk_score,
        "role": u.role
    } for u in active_users]

@router.get("/api/admin/inquiries")
async def admin_get_inquiries(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    inquiries = db.query(Inquiry).order_by(Inquiry.created_at.desc()).all()
    return [{
        "id": i.id,
        "sender_name": i.sender_name,
        "sender_email": i.sender_email,
        "subject": i.subject,
        "message": i.message,
        "created_at": (i.created_at.isoformat() + "Z") if i.created_at else None
    } for i in inquiries]

@router.delete("/api/admin/inquiries/{inquiry_id}")
async def admin_delete_inquiry(
    inquiry_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    inquiry = db.query(Inquiry).filter(Inquiry.id == inquiry_id).first()
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    db.delete(inquiry)
    db.commit()
    return {"message": "Inquiry deleted successfully"}


# ---------------- Advanced SOC Dashboard Endpoints ----------------


@router.get("/api/network-graph")
async def get_network_graph(db: Session = Depends(get_db)):
    return {
        "nodes": [{"id": "Core-Switch", "group": 1}, {"id": "User-Seg-1", "group": 2}, {"id": "DMZ", "group": 3}],
        "links": [{"source": "Core-Switch", "target": "User-Seg-1", "value": 1}, {"source": "Core-Switch", "target": "DMZ", "value": 1}]
    }

@router.get("/api/events")
async def get_dashboard_events(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Activity)
    
    # Filter by user if not admin
    if current_user.role != "admin":
        query = query.filter(Activity.user_id == current_user.id)
        
    activities = query.order_by(Activity.login_time.desc()).limit(10).all()
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

# ---------------- New Location Tracking ----------------

@router.get("/location-tracker")
async def location_tracker_page(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("location_tracker.html", {"request": request, "user": current_user, "google_maps_api_key": Config.GOOGLE_MAPS_API_KEY})

@router.get("/interactive-map")
async def interactive_map_page(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("interactive_map.html", {"request": request, "user": current_user, "google_maps_api_key": Config.GOOGLE_MAPS_API_KEY})


@router.get("/api/dashboard/locations")
async def get_latest_locations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns the most recent location for each user, falling back to Activity table."""
    from sqlalchemy import func
    
    # 1. Get latest from Location table
    subquery_loc = db.query(
        Location.user_id,
        func.max(Location.timestamp).label('max_ts')
    ).group_by(Location.user_id).subquery()

    latest_locs = db.query(Location).join(
        subquery_loc,
        (Location.user_id == subquery_loc.c.user_id) & (Location.timestamp == subquery_loc.c.max_ts)
    ).all()

    locations_map = {loc.user_id: {
        "user_id": loc.user_id,
        "username": loc.user.username if loc.user else "Unknown",
        "lat": loc.latitude,
        "lon": loc.longitude,
        "timestamp": loc.timestamp.isoformat() + "Z",
        "source": "gps"
    } for loc in latest_locs}

    # 2. Fallback to Activity table for users missing in Location table
    # This ensures those who haven't started "Live Tracking" still show up at login location
    all_user_ids = [u.id for u in db.query(User.id).all()]
    missing_user_ids = [uid for uid in all_user_ids if uid not in locations_map]
    
    if missing_user_ids:
        subquery_act = db.query(
            Activity.user_id,
            func.max(Activity.login_time).label('max_ts')
        ).filter(Activity.user_id.in_(missing_user_ids), Activity.status == 'success').group_by(Activity.user_id).subquery()
        
        fallback_locs = db.query(Activity).join(
            subquery_act,
            (Activity.user_id == subquery_act.c.user_id) & (Activity.login_time == subquery_act.c.max_ts)
        ).all()
        
        for act in fallback_locs:
            if act.latitude and act.longitude:
                locations_map[act.user_id] = {
                    "user_id": act.user_id,
                    "username": act.user.username if act.user else "Unknown",
                    "lat": act.latitude,
                    "lon": act.longitude,
                    "timestamp": act.login_time.isoformat() + "Z",
                    "source": "ip"
                }

    # 3. Filter by Role & Valid coordinates
    is_admin = current_user.role == 'admin'
    
    final_locations = []
    for uid, loc_data in locations_map.items():
        # Privacy: Standard users only see their own position point
        if not is_admin and uid != current_user.id:
            continue
            
        # Quality: Skip 0,0 (Null Island / No Data)
        if loc_data.get("lat") == 0.0 and loc_data.get("lon") == 0.0:
            continue
            
        final_locations.append(loc_data)

    return final_locations

@router.websocket("/ws/location")
async def websocket_location(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except Exception:
        manager.disconnect(websocket)
    finally:
        manager.disconnect(websocket)

