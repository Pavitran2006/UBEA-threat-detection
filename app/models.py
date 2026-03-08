from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
import uuid


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(50), primary_key=True, default=lambda: f"tnt_{uuid.uuid4().hex[:12]}")
    name = Column(String(120), nullable=False, unique=True, index=True)
    region = Column(String(30), nullable=False, default="us-east-1")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    subscriptions = relationship("TenantSubscription", back_populates="tenant")
    ml_configs = relationship("TenantMLConfig", back_populates="tenant")


class TenantSubscription(Base):
    __tablename__ = "tenant_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), index=True, nullable=False)
    tier = Column(String(30), nullable=False, default="starter")
    status = Column(String(20), nullable=False, default="active")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="subscriptions")


class TenantMLConfig(Base):
    __tablename__ = "tenant_ml_configs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), index=True, nullable=False)
    retraining_enabled = Column(Boolean, default=True)
    canary_model_version = Column(String(60), nullable=True)
    baseline_model_version = Column(String(60), nullable=True)
    drift_threshold = Column(Float, default=0.25)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="ml_configs")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(50), index=True, nullable=False, default='default')
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)
    role = Column(String(20), default="user") # admin, user
    risk_score = Column(Float, default=0.0) # Added from legacy model
    
    # OAuth Fields
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    github_id = Column(String(255), unique=True, nullable=True, index=True)
    microsoft_id = Column(String(255), unique=True, nullable=True, index=True)
    
    # Account Status
    is_active = Column(Boolean, default=True)
    status = Column(String(20), default="Enabled")
    email_verified = Column(Boolean, default=False)
    is_suspicious = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    activities = relationship("Activity", back_populates="user")
    user_activities = relationship("UserActivity", back_populates="user")
    login_activities = relationship("LoginActivity", back_populates="user")
    security_alerts = relationship("SecurityAlert", back_populates="user")
    alerts = relationship("Alert", back_populates="user")
    password_resets = relationship("PasswordResetToken", back_populates="user")
    
    def __repr__(self):
        return f'<User {self.username}>'

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    token = Column(String(500), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="password_resets")
    
    def __repr__(self):
        return f'<PasswordResetToken for User {self.user_id}>'


class Activity(Base):
    __tablename__ = 'activities'
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(50), index=True, nullable=False, default='default')
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    login_time = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45))
    device_info = Column(String(255))
    location = Column(String(100))
    
    status = Column(String(20), default='success')
    device_fingerprint = Column(String(64))
    session_duration = Column(Integer, default=0)

    user = relationship("User", back_populates="activities")

    def __repr__(self):
        return f'<Activity {self.id} for User {self.user_id}>'


class UserActivity(Base):
    __tablename__ = "user_activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ip_address = Column(String(45))
    login_time = Column(DateTime, default=datetime.utcnow, index=True)
    device_info = Column(String(255))
    location = Column(String(100))
    activity_type = Column(String(50), nullable=False, default="login")
    risk_score = Column(Float, default=0.0)

    user = relationship("User", back_populates="user_activities")

    def __repr__(self):
        return f"<UserActivity {self.id} ({self.activity_type}) for User {self.user_id}>"


class LoginActivity(Base):
    __tablename__ = "login_activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ip_address = Column(String(45), index=True)
    country = Column(String(60), default="Unknown")
    city = Column(String(80), default="Unknown")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    device_info = Column(String(255))
    login_time = Column(DateTime, default=datetime.utcnow, index=True)
    risk_score = Column(Float, default=0.0)

    user = relationship("User", back_populates="login_activities")

    def __repr__(self):
        return f"<LoginActivity {self.id} user={self.user_id} ip={self.ip_address}>"


class SecurityAlert(Base):
    __tablename__ = "security_alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    alert_type = Column(String(80), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), default="Low", index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    verdict = Column(String(20), default="pending")

    user = relationship("User", back_populates="security_alerts")

    def __repr__(self):
        return f"<SecurityAlert {self.id} severity={self.severity}>"


class Alert(Base):
    __tablename__ = 'alerts'
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(50), index=True, nullable=False, default='default')
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    anomaly_score = Column(Float, nullable=False)
    risk_level = Column(String(20))
    detected_at = Column(DateTime, default=datetime.utcnow)

    # network details attached to suspicious logins
    ip_address = Column(String(45))
    
    feedback_status = Column(String(20), default='pending')
    feedback_notes = Column(Text)

    user = relationship("User", back_populates="alerts")

    def __repr__(self):
        return f'<Alert {self.id} (Score: {self.anomaly_score})>'


class AnomalyAlert(Base):
    __tablename__ = 'anomaly_alerts'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    anomaly_score = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    risk_level = Column(String(20))

    user = relationship("User")

    def __repr__(self):
        return f'<AnomalyAlert {self.id} (Score: {self.anomaly_score})>'
