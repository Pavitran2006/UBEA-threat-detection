from datetime import datetime
from . import db

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(50), index=True, nullable=False, default='default')
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False) # Store hashed passwords!
    role = db.Column(db.String(20), default='user')
    risk_score = db.Column(db.Float, default=0.0)
    last_risk_calculation = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    activities = db.relationship('Activity', backref='user', lazy=True)
    alerts = db.relationship('Alert', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'
