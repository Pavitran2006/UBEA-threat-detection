from flask import Blueprint, jsonify, session
from services.dashboard_service import DashboardService

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/stats', methods=['GET'])
def get_stats():
    """Endpoint for dashboard statistics."""
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    response, status_code = DashboardService.get_dashboard_stats()
    return jsonify(response), status_code
from models.alert import Alert

@dashboard_bp.route('/alerts', methods=['GET'])
def get_alerts():
    """Fetches all recent alerts for the dashboard."""
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        alerts = Alert.query.order_by(Alert.detected_at.desc()).limit(20).all()
        return jsonify([{
            "id": a.id,
            "username": a.user.username,
            "score": round(a.anomaly_score, 4),
            "level": a.risk_level,
            "time": a.detected_at.strftime('%H:%M:%S'),
            "status": a.feedback_status
        } for a in alerts]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
