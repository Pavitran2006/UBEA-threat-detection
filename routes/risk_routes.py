from flask import Blueprint, jsonify
from services.risk_service import RiskService
from models.user import User

risk_bp = Blueprint('risk', __name__)

@risk_bp.route('/user-risk', methods=['GET'])
def get_all_user_risk():
    """Fetches risk scores for all users."""
    try:
        users = User.query.all()
        risk_data = []
        
        for user in users:
            # Trigger a re-calculation for up-to-date decay/scores
            current_score = RiskService.calculate_user_risk(user.id) or user.risk_score
            classification = RiskService.get_risk_classification(current_score)
            
            risk_data.append({
                "username": user.username,
                "risk_score": round(current_score, 2),
                "risk_level": classification
            })
            
        return jsonify(risk_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
