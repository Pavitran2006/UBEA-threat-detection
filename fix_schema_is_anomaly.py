import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(override=True)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "ueba_system")
DB_PORT = os.getenv("DB_PORT", "3306")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

def update_schema():
    with engine.connect() as conn:
        print(f"Checking for 'is_anomaly' column in 'activities' table...")
        try:
            # Check if column exists
            result = conn.execute(text("SHOW COLUMNS FROM activities LIKE 'is_anomaly'"))
            if not result.fetchone():
                print("Column 'is_anomaly' not found. Adding it...")
                conn.execute(text("ALTER TABLE activities ADD COLUMN is_anomaly BOOLEAN DEFAULT FALSE"))
                print("Column 'is_anomaly' added successfully.")
            else:
                print("Column 'is_anomaly' already exists.")
            
            # Commit the changes
            conn.commit()
            print("Schema update complete.")
            
        except Exception as e:
            print(f"Error during schema update: {e}")

if __name__ == "__main__":
    update_schema()
