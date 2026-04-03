from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv(override=True)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "ueba_system")
DB_PORT = os.getenv("DB_PORT", "3306")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def fix_mysql_schema():
    print(f"Connecting to {DATABASE_URL}...")
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            print("Changing user_id in security_alerts to be nullable...")
            conn.execute(text("ALTER TABLE security_alerts MODIFY user_id INT NULL;"))
            
            # Also ensure inquiries table exists and is correct
            print("Ensuring inquiries table exists...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS inquiries (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    sender_name VARCHAR(100) NOT NULL,
                    sender_email VARCHAR(100) NOT NULL,
                    subject VARCHAR(200) NOT NULL,
                    message TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            print("Schema fix complete.")
            conn.commit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_mysql_schema()
