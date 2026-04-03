from app.database import engine
from sqlalchemy import text

def add_column_if_not_exists(table, column_name, column_definition):
    with engine.connect() as conn:
        try:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_definition}"))
            print(f"Added column {column_name} to {table}")
            conn.commit()
        except Exception as e:
            if "Duplicate column name" in str(e):
                print(f"Column {column_name} already exists in {table}")
            else:
                print(f"Error adding {column_name} to {table}: {e}")

if __name__ == "__main__":
    print("Updating database schema...")
    # Update Activities
    add_column_if_not_exists("activities", "browser", "VARCHAR(255)")
    add_column_if_not_exists("activities", "device", "VARCHAR(255)")
    add_column_if_not_exists("activities", "city", "VARCHAR(100)")
    add_column_if_not_exists("activities", "country", "VARCHAR(100)")
    add_column_if_not_exists("activities", "latitude", "FLOAT")
    add_column_if_not_exists("activities", "longitude", "FLOAT")
    add_column_if_not_exists("activities", "risk_score", "FLOAT DEFAULT 0.0")

    # Update Users
    add_column_if_not_exists("users", "failed_login_attempts", "INT DEFAULT 0")
    add_column_if_not_exists("users", "locked_until", "DATETIME NULL")
    
    print("Schema update completed.")
