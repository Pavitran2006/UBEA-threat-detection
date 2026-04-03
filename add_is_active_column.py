from app.database import engine
from sqlalchemy import text

def add_column():
    try:
        with engine.connect() as conn:
            # Check if column exists first (optional, but good practice. A failure on ALTER is also caught).
            conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE;"))
            conn.commit()
        print("Column `is_active` added successfully!")
    except Exception as e:
        print(f"Error or column already exists: {e}")

if __name__ == "__main__":
    add_column()
