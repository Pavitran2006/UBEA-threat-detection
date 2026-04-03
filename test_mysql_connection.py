import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "ueba_system")
DB_PORT = os.getenv("DB_PORT", "3306")

print("Testing MySQL connection...")

try:
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=int(DB_PORT)
    )
    cursor = connection.cursor()
    cursor.execute("SELECT 1")
    print("✅ MySQL connection SUCCESSFUL!")
    cursor.execute("SHOW TABLES;")
    tables = cursor.fetchall()
    print("Tables in database:", tables)
    cursor.execute("SELECT COUNT(*) FROM users;")
    user_count = cursor.fetchone()[0]
    print(f"Users count: {user_count}")
    cursor.close()
    connection.close()
except Exception as e:
    print("❌ MySQL connection FAILED:", str(e))
