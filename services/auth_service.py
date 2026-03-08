from app.database import SessionLocal
from app.models import User, Activity
from app.auth import get_password_hash, verify_password
from datetime import datetime
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
            hashed_password = get_password_hash(password)
            
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
            
            if user and verify_password(password, user.hashed_password):
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
