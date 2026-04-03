from app.database import engine
from sqlalchemy import text

def add_columns():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE activities ADD COLUMN status VARCHAR(20) DEFAULT 'success'"))
            conn.commit()
            print("Added status")
        except Exception as e: 
            conn.rollback()
            print("status exists:", e)
        
        try:
            conn.execute(text("ALTER TABLE activities ADD COLUMN device_fingerprint VARCHAR(64)"))
            conn.commit()
            print("Added device_fingerprint")
        except Exception as e: 
            conn.rollback()
            print("device_fingerprint exists:", e)
        
        try:
            conn.execute(text("ALTER TABLE activities ADD COLUMN session_duration INTEGER DEFAULT 0"))
            conn.commit()
            print("Added session_duration")
        except Exception as e: 
            conn.rollback()
            print("session_duration exists:", e)
        
        try:
            conn.execute(text("ALTER TABLE activities ADD COLUMN risk_score FLOAT DEFAULT 0.0"))
            conn.commit()
            print("Added risk_score")
        except Exception as e: 
            conn.rollback()
            print("risk_score exists:", e)
        
        try:
            conn.execute(text("ALTER TABLE activities ADD COLUMN is_anomaly BOOLEAN DEFAULT FALSE"))
            conn.commit()
            print("Added is_anomaly")
        except Exception as e: 
            conn.rollback()
            print("is_anomaly exists:", e)

if __name__ == "__main__":
    add_columns()
