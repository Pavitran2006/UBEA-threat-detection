import sqlite3
import os

def fix_schema():
    db_path = 'ueba.db'
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Fixing security_alerts table schema...")
    try:
        # SQLite doesn't support changing NOT NULL via ALTER TABLE.
        # We must recreate the table.
        
        # 1. Check if user_id is already nullable
        cursor.execute("PRAGMA table_info(security_alerts)")
        cols = cursor.fetchall()
        user_id_col = next((c for c in cols if c[1] == 'user_id'), None)
        
        if user_id_col and user_id_col[3] == 0:
            print("user_id is already nullable. No change needed.")
        else:
            # 2. Rename old table
            cursor.execute("ALTER TABLE security_alerts RENAME TO security_alerts_old")
            
            # 3. Create new table with nullable user_id
            cursor.execute("""
                CREATE TABLE security_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id VARCHAR(50) DEFAULT 'default',
                    user_id INTEGER,
                    alert_type VARCHAR(50) NOT NULL,
                    severity VARCHAR(20) DEFAULT 'medium',
                    description TEXT,
                    ip_address VARCHAR(45),
                    timestamp DATETIME,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)
            
            # 4. Copy data
            cursor.execute("""
                INSERT INTO security_alerts (id, tenant_id, user_id, alert_type, severity, description, ip_address, timestamp)
                SELECT id, tenant_id, user_id, alert_type, severity, description, ip_address, timestamp FROM security_alerts_old
            """)
            
            # 5. Drop old table
            cursor.execute("DROP TABLE security_alerts_old")
            print("security_alerts table updated successfully.")
            
        # Also ensure inquiries table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inquiries'")
        if not cursor.fetchone():
            print("Creating inquiries table...")
            cursor.execute("""
                CREATE TABLE inquiries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_name VARCHAR(100) NOT NULL,
                    sender_email VARCHAR(100) NOT NULL,
                    subject VARCHAR(200) NOT NULL,
                    message TEXT NOT NULL,
                    created_at DATETIME
                )
            """)
            print("inquiries table created successfully.")
        else:
            print("inquiries table already exists.")

        conn.commit()
    except Exception as e:
        print(f"Error during schema fix: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_schema()
