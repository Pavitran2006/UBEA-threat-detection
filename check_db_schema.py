import sqlite3
import os

db_path = 'ueba_app.db'
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        print("Columns in 'users' table:")
        for col in columns:
            print(col)
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print("\nAll tables:")
        for t in tables:
            print(t)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
