from app.database import SessionLocal
from app.models import User, Activity
from app.auth import hash_password
from app.otp_service import generate_otp, send_email_otp, otp_expiry
from datetime import datetime, timedelta
import hashlib
import logging

logger = logging.getLogger(__name__)

class AuthService:
    @staticmethod
    def register_user(db, username, email, password, role='user'):
        """Register a new user with the given credentials."""
        try:
            # Check if user already exists
            if db.query(User).filter_by(username=username).first():
                return {"error": "Username already exists"}, 400
            if db.query(User).filter_by(email=email).first():
                return {"error": "Email already exists"}, 400

            # Hash the password
            hashed_password = hash_password(password)
            
            # Create new user
            new_user = User(
                username=username,
                email=email,
                hashed_password=hashed_password,
                role=role,
                tenant_id='default'
            )
            
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            return {"message": "User registered successfully", "user_id": new_user.id}, 201
        except Exception as e:
            db.rollback()
            logger.error(f"Registration error: {str(e)}")
            return {"error": "Registration failed"}, 500

    @staticmethod
    def login_user(db, identifier, password, client_ip='Unknown', user_agent='Unknown'):
        """Authenticate user and record login activity."""
        try:
            # Find user by username or email
            from sqlalchemy import func, or_
            user = db.query(User).filter(
                or_(
                    func.lower(User.email) == identifier.lower(),
                    func.lower(User.username) == identifier.lower()
                )
            ).first()
            
            # Create a fingerprint
            fingerprint = hashlib.sha256(f"{client_ip}{user_agent}".encode()).hexdigest()
            
            if user and user.verify_password(password):
                # Capture Successful Login Activity
                login_activity = Activity(
                    user_id=user.id,
                    login_time=datetime.utcnow(),
                    ip_address=client_ip,
                    device_info=user_agent,
                    location="Unknown",
                    status='success',
                    device_fingerprint=fingerprint,
                    tenant_id='default'
                )
                db.add(login_activity)
                
                # Update User record with last login info
                user.last_login = datetime.utcnow()
                user.last_login_ip = client_ip
                
                db.commit()
                
                # Trigger Anomaly Detection & Risk Scoring (optional, non-blocking)
                try:
                    from services.ml_service import MLService
                    from services.risk_service import RiskService
                    anom_result = MLService.predict_anomaly(db, user.id)
                    RiskService.calculate_user_risk(db, user.id)
                except Exception as e:
                    logger.warning(f"Non-blocking Anomaly/Risk Error: {e}")

                return {
                    "message": "Login successful",
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "role": user.role
                    }
                }, 200
            
            # Log Failed Attempt if user exists
            if user:
                failed_activity = Activity(
                    user_id=user.id,
                    login_time=datetime.utcnow(),
                    ip_address=client_ip,
                    device_info=user_agent,
                    status='failed',
                    device_fingerprint=fingerprint,
                    tenant_id='default'
                )
                db.add(failed_activity)
                db.commit()
            
            return {"error": "Invalid username or password"}, 401
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return {"error": "Login failed"}, 500

    @staticmethod
    def forgot_password(db, email):
        """Send reset OTP to user email."""
        user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
        if not user:
            return {"error": "Email not found"}, 404
        
        otp = generate_otp()
        expiry = otp_expiry()
        
        user.otp_code = otp
        user.otp_expiry = expiry
        user.otp_attempts = 0
        user.otp_request_count = getattr(user, 'otp_request_count', 0) + 1
        user.otp_sent_at = datetime.utcnow()
        
        db.commit()
        
        send_email_otp(email, otp)
        
        return {"message": "OTP sent to your email"}, 200

    @staticmethod
    def verify_reset_otp(db, email, otp):
        """Verify reset OTP."""
        user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
        if not user:
            return False, "Email not found"
        
        if user.otp_attempts >= 3:
            return False, "Max attempts exceeded"
        
        if not user.otp_code or not user.otp_expiry or user.otp_expiry < datetime.utcnow():
            return False, "OTP expired or invalid"
        
        if user.otp_code == otp:
            user.otp_attempts = 0
            db.commit()
            return True, "Valid OTP"
        
        user.otp_attempts += 1
        db.commit()
        return False, "Invalid OTP"

    @staticmethod
    def reset_password(db, email, new_password):
        """Reset user password after OTP verification."""
        user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
        if not user:
            return False, "Email not found"
        
        hashed_password = hash_password(new_password)
        user.hashed_password = hashed_password
        
        # Clear OTP fields
        user.otp_code = None
        user.otp_expiry = None
        user.otp_attempts = 0
        
        db.commit()
        return True, "Password reset successful"
