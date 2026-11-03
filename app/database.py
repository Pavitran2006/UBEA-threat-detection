import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger("ueba.database")

raw_db_url = os.getenv("DATABASE_URL")

if raw_db_url:
    # Render and cloud providers supply "postgres://" or "postgresql://"
    # Ensure SQLAlchemy routes directly to the installed psycopg (v3) driver
    if raw_db_url.startswith("postgres://"):
        DATABASE_URL = raw_db_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif raw_db_url.startswith("postgresql://") and not raw_db_url.startswith("postgresql+"):
        DATABASE_URL = raw_db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    else:
        DATABASE_URL = raw_db_url

else:
    db_type = os.getenv("DB_TYPE", "mysql" if os.getenv("DB_HOST") else "sqlite").lower()
    if db_type == "mysql" and os.getenv("DB_HOST"):
        db_user = os.getenv("DB_USER", os.getenv("DB_USERNAME", "root"))
        db_pass = os.getenv("DB_PASSWORD", "")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "3306")
        db_name = os.getenv("DB_NAME", "ueba_system")
        DATABASE_URL = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    else:
        DATABASE_URL = "sqlite:///ueba.db"

# Engine configuration with pooling & pre-ping for cloud reliability
engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_recycle"] = 300
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_db_connection() -> tuple[bool, str]:
    """Test database connectivity safely without throwing unhandled exceptions."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Database connection operational"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False, str(e)