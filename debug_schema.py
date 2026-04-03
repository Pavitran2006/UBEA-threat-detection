import sqlite3

def check_schema():
    conn = sqlite3.connect('ueba.db')
    cursor = conn.cursor()
    
    tables = ['security_alerts', 'inquiries']
    
    for table in tables:
        print(f"\n--- Schema for {table} ---")
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            for col in columns:
                # cid, name, type, notnull, dflt_value, pk
                print(col)
        except Exception as e:
            print(f"Error checking {table}: {e}")
            
    conn.close()

if __name__ == "__main__":
    check_schema()
