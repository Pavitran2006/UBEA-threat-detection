import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def apply_migrations():
    # Connect to MySQL directly to execute ALTER statements
    host = os.getenv("DB_HOST", "localhost")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    database = os.getenv("DB_NAME", "ueba_system")
    port = int(os.getenv("DB_PORT", "3306"))

    try:
        connection = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            # 1. Add missing users columns
            columns_to_add = [
                ("phone", "VARCHAR(30) NULL"),
                ("status", "VARCHAR(20) DEFAULT 'active'"),
                ("is_verified", "BOOLEAN DEFAULT FALSE"),
                ("otp_code", "VARCHAR(10) NULL"),
                ("otp_expiry", "DATETIME NULL"),
                ("otp_attempts", "INT DEFAULT 0"),
                ("otp_request_count", "INT DEFAULT 0"),
                ("otp_sent_at", "DATETIME NULL"),
            ]
            
            for col_name, col_type in columns_to_add:
                try:
                    # Check if exists first
                    cursor.execute(f"SHOW COLUMNS FROM users LIKE '{col_name}'")
                    if not cursor.fetchone():
                        cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                        print(f"Added column {col_name}")
                    else:
                        print(f"Column {col_name} already exists")
                except Exception as e:
                    print(f"Warning on {col_name}: {e}")
                    
            # Check if password column needs rename to hashed_password
            cursor.execute("SHOW COLUMNS FROM users LIKE 'password'")
            if cursor.fetchone():
                try:
                    cursor.execute("ALTER TABLE users CHANGE COLUMN password hashed_password VARCHAR(255) NOT NULL")
                    print("Renamed 'password' to 'hashed_password'")
                except Exception as e:
                    print(f"Warning on renaming password: {e}")
                    
            # 2. Create password_reset_tokens table if it doesn't exist
            create_tokens_table = """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tenant_id VARCHAR(50) NOT NULL DEFAULT 'default',
                user_id INT NOT NULL,
                token VARCHAR(255) NOT NULL UNIQUE,
                expires_at DATETIME NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
            cursor.execute(create_tokens_table)
            print("Ensured password_reset_tokens table exists")
            
        connection.commit()
        print("Migrations applied successfully!")
        
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        if 'connection' in locals() and connection:
            connection.close()

if __name__ == "__main__":
    apply_migrations()
