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

def check_schema():
    with engine.connect() as conn:
        try:
            result = conn.execute(text("DESCRIBE users"))
            columns = result.fetchall()
            with open("users_schema.txt", "w") as f:
                f.write(f"Columns for 'users' table in database '{DB_NAME}':\n")
                for col in columns:
                    f.write(f" - {col[0]} ({col[1]})\n")
            print("Schema written to users_schema.txt")
        except Exception as e:
            print(f"Error checking schema: {e}")

if __name__ == "__main__":
    check_schema()
