from __future__ import annotations

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..config import (
    OTP_EXPIRE_MINUTES,
    OTP_MAX_ATTEMPTS,
    OTP_RATE_LIMIT_MAX,
    OTP_RATE_LIMIT_WINDOW_MINUTES,
    MFA_LOGIN_ENABLED,
)
from ..database import get_db
from ..models.user import User, PasswordResetToken, LoginActivity, OtpCode, LoginLog
from ..auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
    generate_password_reset_token,
    get_password_reset_token_expiry,
    revoke_token,
)
from ..security import get_current_user
from ..services.otp_service import generate_otp, send_email_otp, send_test_email
from ..services.sms_service import send_sms_otp
from ..services.risk_engine import RiskSignal, calculate_risk_score

router = APIRouter()


async def _get_payload(request: Request) -> dict:
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    form = await request.form()
    return dict(form)


def _is_email(identifier: str) -> bool:
    return "@" in identifier


async def _send_otp(user: User, otp: str, identifier: str) -> None:
    if _is_email(identifier):
        await send_email_otp(user.email, otp)
    else:
        await send_sms_otp(user.phone or identifier, otp)


@router.post("/signup")
async def signup(request: Request, db: Session = Depends(get_db)):
    payload = await _get_payload(request)
    full_name = (payload.get("full_name") or payload.get("name") or "").strip()
    username = (payload.get("username") or full_name or "").strip()
    email = (payload.get("email") or "").strip().lower()
    phone = (payload.get("phone") or "").strip() or None
    password = payload.get("password") or ""
    confirm_password = payload.get("confirm_password") or payload.get("confirmPassword") or ""

    if not username or not email or not password:
        raise HTTPException(status_code=400, detail="Missing required fields")
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    existing = (
        db.query(User)
        .filter((User.email == email) | (User.username == username))
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="User already registered")

    user = User(
        tenant_id="default",
        username=username,
        email=email,
        phone=phone,
        password_hash=hash_password(password),
        status="active",
        is_verified=False,
    )
    db.add(user)
    db.commit()

    otp = generate_otp()
    user.otp_code = otp
    user.otp_expiry = datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)
    user.otp_attempts = 0
    user.otp_request_count = 1
    user.otp_sent_at = datetime.utcnow()
    db.query(OtpCode).filter(OtpCode.user_id == user.id).delete()
    db.add(
        OtpCode(
            user_id=user.id,
            email=user.email,
            otp_code=otp,
            otp_expiry=user.otp_expiry,
            purpose="signup",
        )
    )
    db.commit()

    try:
        await _send_otp(user, otp, email)
    except Exception as exc:
        print("OTP Email Error:", exc)
        raise HTTPException(status_code=500, detail="Failed to send OTP")

    return JSONResponse(
        status_code=201,
        content={"message": "Signup successful. OTP sent for verification."},
    )


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    payload = await _get_payload(request)
    identifier = (payload.get("email") or payload.get("username") or "").strip().lower()
    password = payload.get("password") or ""

    if not identifier or not password:
        raise HTTPException(status_code=400, detail="Missing credentials")

    user = (
        db.query(User)
        .filter((User.email == identifier) | (User.username == identifier))
        .first()
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email/username or password")

    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email/username or password")

    if user.status == "disabled":
        raise HTTPException(status_code=403, detail="Account disabled")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Account not verified")

    if MFA_LOGIN_ENABLED:
        otp = generate_otp()
        user.otp_code = otp
        user.otp_expiry = datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)
        user.otp_attempts = 0
        user.otp_request_count = 1
        user.otp_sent_at = datetime.utcnow()
        db.query(OtpCode).filter(OtpCode.user_id == user.id).delete()
        db.add(
            OtpCode(
                user_id=user.id,
                email=user.email,
                otp_code=otp,
                otp_expiry=user.otp_expiry,
                purpose="login",
            )
        )
        db.commit()
        try:
            await _send_otp(user, otp, user.email)
        except Exception as exc:
            print("OTP Email Error:", exc)
            raise HTTPException(status_code=500, detail="Failed to send OTP")
        return {"mfa_required": True, "message": "OTP sent for login verification"}

    ua = request.headers.get("user-agent", "Unknown")
    ip_address = request.client.host if request.client else "Unknown"

    last_login = (
        db.query(LoginActivity)
        .filter(LoginActivity.user_id == user.id)
        .order_by(LoginActivity.login_time.desc())
        .first()
    )

    signal = RiskSignal(
        is_new_device=last_login is not None and (last_login.device or "") != ua,
        is_new_location=False,
        failed_attempts=0,
        ip_reputation_score=0.0,
        login_hour=datetime.utcnow().hour,
    )

    risk_score = calculate_risk_score(signal)

    activity = LoginActivity(
        user_id=user.id,
        ip_address=ip_address,
        device=ua,
        browser=ua,
        login_time=datetime.utcnow(),
        risk_score=risk_score,
    )
    db.add(activity)
    db.add(
        LoginLog(
            user_id=user.id,
            user_email=user.email,
            login_time=datetime.utcnow(),
            ip_address=ip_address,
        )
    )

    user.last_login = datetime.utcnow()
    user.risk_score = risk_score
    db.commit()

    access_token = create_access_token(data={"sub": user.email, "uid": user.id})
    refresh_token = create_refresh_token(data={"sub": user.email, "uid": user.id})
    return JSONResponse(
        status_code=200,
        content={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "role": user.role,
            },
        },
    )


@router.post("/refresh")
async def refresh_token(request: Request):
    payload = await _get_payload(request)
    token = payload.get("refresh_token") or ""
    decoded = decode_refresh_token(token)
    if not decoded:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    access_token = create_access_token(data={"sub": decoded.get("sub"), "uid": decoded.get("uid")})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role or "user",
    }


@router.post("/logout")
async def logout(request: Request):
    payload = await _get_payload(request)
    refresh_token_value = payload.get("refresh_token") or ""
    if refresh_token_value:
        revoke_token(refresh_token_value)
    return {"status": "logged_out"}


@router.post("/send-otp")
async def send_otp(request: Request, db: Session = Depends(get_db)):
    payload = await _get_payload(request)
    identifier = (payload.get("identifier") or payload.get("email") or payload.get("phone") or "").strip()
    purpose = (payload.get("purpose") or "reset").lower()

    if not identifier:
        raise HTTPException(status_code=400, detail="Missing identifier")

    user = (
        db.query(User)
        .filter((User.email == identifier) | (User.phone == identifier))
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.utcnow()
    if user.otp_sent_at and user.otp_sent_at > now - timedelta(minutes=OTP_RATE_LIMIT_WINDOW_MINUTES):
        if (user.otp_request_count or 0) >= OTP_RATE_LIMIT_MAX:
            raise HTTPException(status_code=429, detail="OTP rate limit exceeded")
    else:
        user.otp_request_count = 0

    otp = generate_otp()
    user.otp_code = otp
    user.otp_expiry = now + timedelta(minutes=OTP_EXPIRE_MINUTES)
    user.otp_request_count = (user.otp_request_count or 0) + 1
    user.otp_attempts = 0
    user.otp_sent_at = now
    db.query(OtpCode).filter(OtpCode.user_id == user.id).delete()
    db.add(
        OtpCode(
            user_id=user.id,
            email=user.email,
            otp_code=otp,
            otp_expiry=user.otp_expiry,
            purpose=purpose,
        )
    )
    db.commit()

    try:
        await _send_otp(user, otp, identifier)
    except Exception as exc:
        print("OTP Email Error:", exc)
        raise HTTPException(status_code=500, detail="Failed to send OTP")

    return {"status": "success", "message": "OTP sent", "purpose": purpose}


@router.post("/forgot-password")
async def forgot_password(request: Request, db: Session = Depends(get_db)):
    payload = await _get_payload(request)
    email = (payload.get("email") or "").strip().lower()

    if not email:
        raise HTTPException(status_code=400, detail="Missing email")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    otp = generate_otp()
    now = datetime.utcnow()
    user.otp_code = otp
    user.otp_expiry = now + timedelta(minutes=OTP_EXPIRE_MINUTES)
    user.otp_request_count = (user.otp_request_count or 0) + 1
    user.otp_attempts = 0
    user.otp_sent_at = now
    db.query(OtpCode).filter(OtpCode.user_id == user.id).delete()
    db.add(
        OtpCode(
            user_id=user.id,
            email=user.email,
            otp_code=otp,
            otp_expiry=user.otp_expiry,
            purpose="reset",
        )
    )
    db.commit()

    try:
        await _send_otp(user, otp, email)
    except Exception as exc:
        print("OTP Email Error:", exc)
        raise HTTPException(status_code=500, detail="Failed to send OTP")

    return {"status": "success", "message": "OTP sent"}


@router.post("/verify-otp")
async def verify_otp_api(request: Request, db: Session = Depends(get_db)):
    payload = await _get_payload(request)
    identifier = (payload.get("identifier") or payload.get("email") or payload.get("phone") or "").strip()
    otp = (payload.get("otp") or "").strip()
    purpose = (payload.get("purpose") or "reset").lower()

    if not identifier or not otp:
        raise HTTPException(status_code=400, detail="Missing otp or identifier")

    user = (
        db.query(User)
        .filter((User.email == identifier) | (User.phone == identifier))
        .first()
    )
    if not user or not user.otp_code:
        raise HTTPException(status_code=404, detail="OTP not found")

    if user.otp_expiry and user.otp_expiry.replace(tzinfo=None) < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP expired")

    if (user.otp_attempts or 0) >= OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="OTP attempts exceeded")

    if user.otp_code != otp:
        user.otp_attempts = (user.otp_attempts or 0) + 1
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid OTP")

    user.otp_code = None
    user.otp_expiry = None
    user.otp_attempts = 0
    user.otp_request_count = 0
    db.query(OtpCode).filter(OtpCode.user_id == user.id).delete()

    if purpose == "signup":
        user.is_verified = True
        db.commit()
        return {"status": "verified"}

    if purpose == "login":
        db.commit()
        access_token = create_access_token(data={"sub": user.email, "uid": user.id})
        refresh_token = create_refresh_token(data={"sub": user.email, "uid": user.id})
        ip_address = request.client.host if request.client else "Unknown"
        db.add(
            LoginLog(
                user_id=user.id,
                user_email=user.email,
                login_time=datetime.utcnow(),
                ip_address=ip_address,
            )
        )
        db.commit()
        return {
            "status": "verified",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    reset_token = generate_password_reset_token()
    reset_entry = PasswordResetToken(
        user_id=user.id,
        token=reset_token,
        expires_at=get_password_reset_token_expiry(),
        channel="otp",
    )
    db.add(reset_entry)
    db.commit()
    return {"status": "verified", "reset_token": reset_token}


@router.post("/reset-password")
async def reset_password_api(request: Request, db: Session = Depends(get_db)):
    payload = await _get_payload(request)
    token = (payload.get("reset_token") or "").strip()
    password = payload.get("password") or ""
    confirm_password = payload.get("confirm_password") or ""

    if not token or not password:
        raise HTTPException(status_code=400, detail="Missing reset token or password")
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    reset_token = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token == token, PasswordResetToken.used == False)
        .first()
    )
    if not reset_token or reset_token.expires_at.replace(tzinfo=None) < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(password)
    reset_token.used = True
    db.commit()
    return {"status": "password_updated"}


@router.post("/smtp-test")
async def smtp_test(request: Request):
    payload = await _get_payload(request)
    to_email = (payload.get("email") or payload.get("to") or "").strip() or None
    try:
        send_test_email(to_email)
        return {"status": "ok", "message": "Test email sent"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SMTP test failed: {exc}")


@router.get("/smtp-test")
async def smtp_test_get(email: str | None = None):
    try:
        send_test_email(email)
        return {"status": "ok", "message": "Test email sent"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SMTP test failed: {exc}")
