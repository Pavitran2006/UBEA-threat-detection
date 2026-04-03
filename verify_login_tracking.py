import sqlite3
import os

db_path = 'ueba.db'
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Check columns in users table
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    col_names = [col[1] for col in columns]
    
    required_cols = ['last_login', 'last_login_ip']
    for col in required_cols:
        if col in col_names:
            print(f"✅ Column '{col}' exists in 'users' table.")
        else:
            print(f"❌ Column '{col}' MISSING in 'users' table.")
            # Let's try to add them if they are missing (for local testing environment)
            try:
                if col == 'last_login':
                    cursor.execute("ALTER TABLE users ADD COLUMN last_login DATETIME")
                else:
                    cursor.execute("ALTER TABLE users ADD COLUMN last_login_ip VARCHAR(45)")
                conn.commit()
                print(f"  -> Added column '{col}' successfully.")
            except Exception as e:
                print(f"  -> Failed to add column '{col}': {e}")

except Exception as e:
    print(f"Error during verification: {e}")
finally:
    conn.close()
