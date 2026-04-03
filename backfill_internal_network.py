import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Add parent directory to sys.path if needed
sys.path.append(os.getcwd())

load_dotenv(override=True)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "ueba_system")
DB_PORT = os.getenv("DB_PORT", "3306")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print(f"Connecting to database: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

try:
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Rule: 127.0.0.1 or private IP ranges
    # 127.*, 10.*, 192.168.*, 172.16.*-172.31.*, ::1
    
    query = text("""
        UPDATE activities 
        SET location = 'Internal Network',
            city = 'Internal',
            country = 'Network'
        WHERE ip_address = '127.0.0.1' 
           OR ip_address = '::1'
           OR ip_address LIKE '192.168.%'
           OR ip_address LIKE '10.%'
           OR ip_address LIKE '172.16.%'
           OR ip_address LIKE '172.17.%'
           OR ip_address LIKE '172.18.%'
           OR ip_address LIKE '172.19.%'
           OR ip_address LIKE '172.20.%'
           OR ip_address LIKE '172.21.%'
           OR ip_address LIKE '172.22.%'
           OR ip_address LIKE '172.23.%'
           OR ip_address LIKE '172.24.%'
           OR ip_address LIKE '172.25.%'
           OR ip_address LIKE '172.26.%'
           OR ip_address LIKE '172.27.%'
           OR ip_address LIKE '172.28.%'
           OR ip_address LIKE '172.29.%'
           OR ip_address LIKE '172.30.%'
           OR ip_address LIKE '172.31.%'
           OR location = 'Unknown, Unknown'
    """)

    result = session.execute(query)
    session.commit()
    
    print(f"Successfully updated {result.rowcount} rows to 'Internal Network'.")
    session.close()

except Exception as e:
    print(f"Error during backfill: {str(e)}")
    sys.exit(1)
