from flask import Blueprint, request, jsonify
from services.ml_service import MLService
from models.alert import Alert
from models import db
import logging

ml_bp = Blueprint('ml', __name__)

@ml_bp.route('/feedback', methods=['POST'])
def submit_feedback():
    """
    Submits feedback for an alert (True/False Threat).
    Triggers model retraining if significant feedback collected.
    """
    data = request.json
    alert_id = data.get('alert_id')
    status = data.get('status') # 'false_positive' or 'confirmed'
    notes = data.get('notes', '')
    
    if not alert_id or status not in ['false_positive', 'confirmed']:
        return jsonify({"error": "Missing alert_id or invalid status"}), 400
        
    try:
        alert = Alert.query.get(alert_id)
        if not alert:
            return jsonify({"error": "Alert not found"}), 404
            
        alert.feedback_status = status
        alert.feedback_notes = notes
        db.session.commit()
        
        # Check if we should retrain
        # Simplified: retrain after every feedback for demo
        MLService.train_model()
        
        return jsonify({"message": "Feedback submitted and model updated."}), 200
    except Exception as e:
        logging.error(f"Feedback Error: {e}")
        return jsonify({"error": "Failed to submit feedback"}), 500

@ml_bp.route('/retrain', methods=['POST'])
def force_retrain():
    """Manually triggers model retraining."""
    if MLService.train_model():
        return jsonify({"message": "Model retrained successfully."}), 200
    return jsonify({"error": "Retraining failed (insufficient data?)"}), 400
