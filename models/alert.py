from datetime import datetime
from . import db

class Alert(db.Model):
    __tablename__ = 'alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(50), index=True, nullable=False, default='default')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    anomaly_score = db.Column(db.Float, nullable=False)
    risk_level = db.Column(db.String(20)) # Low, Medium, High, Critical
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # ML Feedback Loop Fields
    feedback_status = db.Column(db.String(20), default='pending') # pending, false_positive, confirmed
    feedback_notes = db.Column(db.Text)

    def __repr__(self):
        return f'<Alert {self.id} (Score: {self.anomaly_score})>'
