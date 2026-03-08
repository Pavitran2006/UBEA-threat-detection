from app.models import User, Activity, Alert
import logging

logger = logging.getLogger(__name__)

class DashboardService:
    @staticmethod
    def get_dashboard_stats(db):
        """Fetches counts for users, activities, and alerts."""
        try:
            user_count = db.query(User).count()
            activity_count = db.query(Activity).count()
            alert_count = db.query(Alert).count()
            
            return {
                "users": user_count,
                "signals": activity_count,
                "alerts": alert_count
            }, 200
        except Exception as e:
            logger.error(f"Dashboard stats error: {str(e)}")
            return {"error": f"Database error: {str(e)}"}, 500
