from datetime import datetime
from . import db

class Activity(db.Model):
    __tablename__ = 'activities'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(50), index=True, nullable=False, default='default')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
    device_info = db.Column(db.String(255))
    location = db.Column(db.String(100))
    
    # Advanced Features
    status = db.Column(db.String(20), default='success') # success, failed
    device_fingerprint = db.Column(db.String(64))
    session_duration = db.Column(db.Integer, default=0) # in seconds

    def __repr__(self):
        return f'<Activity {self.id} for User {self.user_id}>'
