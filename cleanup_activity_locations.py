import os
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Activity

def cleanup_locations():
    db = SessionLocal()
    try:
        activities = db.query(Activity).all()
        count = 0
        for activity in activities:
            original = activity.location
            # Case 1: (lat, lon) [Exact GPS]
            # Case 2: City, Country (GPS Verified)
            # Case 3: Just coordinates like (10.95, 77.95)
            
            if not original:
                continue
                
            new_location = original
            
            # If we have city and country fields, use them directly
            if activity.city and activity.country:
                new_location = f"{activity.city}, {activity.country}"
            elif "(" in original and ")" in original:
                # If no city/country but coord-like string, maybe it's internal
                new_location = "Internal Network"
            
            # Strip suffixes anyway
            new_location = new_location.replace(" [Exact GPS]", "").replace(" (GPS Verified)", "")
            
            if new_location != original:
                activity.location = new_location
                count += 1
        
        db.commit()
        print(f"Cleanup complete. Updated {count} activity records.")
    except Exception as e:
        print(f"Error during cleanup: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_locations()
