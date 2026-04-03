from app.database import engine
from sqlalchemy import text

def add_last_activity_column():
    print("Connecting to database...")
    try:
        with engine.connect() as con:
            print("Executing ALTER TABLE...")
            # Use a slightly different approach for compatibility
            con.execute(text("ALTER TABLE users ADD last_activity DATETIME NULL"))
            con.commit()
            print("Column 'last_activity' added successfully.")
    except Exception as e:
        if "Duplicate column name" in str(e):
            print("Column 'last_activity' already exists.")
        else:
            print(f"Error adding column: {e}")

if __name__ == "__main__":
    add_last_activity_column()
