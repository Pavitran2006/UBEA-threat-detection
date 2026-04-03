from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(50), index=True, nullable=False, default='default')
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(30), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    status = Column(String(20), default='active')
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    otp_code = Column(String(10), nullable=True)
    otp_expiry = Column(DateTime, nullable=True)
    otp_attempts = Column(Integer, default=0)
    otp_request_count = Column(Integer, default=0)
    otp_sent_at = Column(DateTime, nullable=True)
    role = Column(String(20), default='user')
    risk_score = Column(Float, default=0.0)
    last_risk_calculation = Column(DateTime, default=datetime.utcnow)
    profile_pic = Column(String(255), nullable=True)
    
    # Login Tracking
    last_login = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    last_activity = Column(DateTime, default=datetime.utcnow)
    
    # Advanced Security Features
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    
    # Relationships
    activities = relationship("Activity", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    security_alerts = relationship("SecurityAlert", back_populates="user", cascade="all, delete-orphan")
    locations = relationship("Location", back_populates="user", cascade="all, delete-orphan")
    password_resets = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.username}>'

class Activity(Base):
    __tablename__ = 'activities'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(50), index=True, nullable=False, default='default')
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    login_time = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45))
    device_info = Column(String(255))
    browser = Column(String(255))
    device = Column(String(255))
    location = Column(String(100))
    city = Column(String(100))
    country = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Advanced Features
    status = Column(String(20), default='success')  # success, failed
    device_fingerprint = Column(String(64))
    session_duration = Column(Integer, default=0)  # in seconds
    risk_score = Column(Float, default=0.0)
    is_anomaly = Column(Boolean, default=False)

    user = relationship("User", back_populates="activities")

    def __repr__(self):
        return f'<Activity {self.id} for User {self.user_id}>'

class SecurityAlert(Base):
    __tablename__ = 'security_alerts'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(50), nullable=False, default='default')
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), default='medium')
    description = Column(Text)
    ip_address = Column(String(45))
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="security_alerts")

    def __repr__(self):
        return f'<SecurityAlert {self.id}: {self.alert_type} - {self.severity}>'


class Alert(Base):
    __tablename__ = 'alerts'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(50), index=True, nullable=False, default='default')
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    anomaly_score = Column(Float, nullable=False)
    risk_level = Column(String(20))  # Low, Medium, High, Critical
    detected_at = Column(DateTime, default=datetime.utcnow)
    
    # ML Feedback Loop Fields
    feedback_status = Column(String(20), default='pending')  # pending, false_positive, confirmed
    feedback_notes = Column(Text)

    user = relationship("User", back_populates="alerts")

    def __repr__(self):
        return f'<Alert {self.id} (Score: {self.anomaly_score})>'

class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    latitude = Column(Float)
    longitude = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="locations")

    def __repr__(self):
        return f'<Location {self.id} for User {self.user_id}>'

class PasswordResetToken(Base):
    __tablename__ = 'password_reset_tokens'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(50), index=True, nullable=False, default='default')
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    
    user = relationship("User", back_populates="password_resets")

    def __repr__(self):
        return f'<PasswordResetToken {self.token[:8]}... for User {self.user_id}>'

class Inquiry(Base):
    __tablename__ = "inquiries"

    id = Column(Integer, primary_key=True, index=True)
    sender_name = Column(String(100), nullable=False)
    sender_email = Column(String(100), nullable=False)
    subject = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

LoginActivity = Activity
AnomalyAlert = Alert
