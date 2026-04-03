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
    tables = ['users', 'activities', 'security_alerts', 'alerts', 'locations', 'password_reset_tokens', 'inquiries']
    with engine.connect() as conn:
        try:
            with open("all_tables_schema.txt", "w") as f:
                for table in tables:
                    f.write(f"\n--- Table: {table} ---\n")
                    try:
                        result = conn.execute(text(f"DESCRIBE {table}"))
                        columns = result.fetchall()
                        for col in columns:
                            f.write(f" - {col[0]} ({col[1]})\n")
                    except Exception as e:
                        f.write(f"Error describing table {table}: {e}\n")
            print("Schema written to all_tables_schema.txt")
        except Exception as e:
            print(f"Error checking schema: {e}")

if __name__ == "__main__":
    check_schema()
