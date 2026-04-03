from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .config import SQLALCHEMY_DATABASE_URL

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_user_columns(engine) -> None:
    """Ensure OTP-related columns exist on legacy databases."""
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns("users")}
    missing_defs = {
        "is_verified": "BOOLEAN DEFAULT 0",
        "otp_code": "VARCHAR(10)",
        "otp_expiry": "DATETIME",
        "otp_attempts": "INTEGER DEFAULT 0",
        "otp_request_count": "INTEGER DEFAULT 0",
        "otp_sent_at": "DATETIME",
    }

    to_add = {name: ddl for name, ddl in missing_defs.items() if name not in existing}
    if not to_add:
        return

    with engine.begin() as conn:
        for name, ddl in to_add.items():
            conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {ddl}"))

        if "is_verified" in to_add and "email_verified" in existing:
            conn.execute(
                text(
                    "UPDATE users SET is_verified = COALESCE(email_verified, 0) "
                    "WHERE is_verified IS NULL"
                )
            )


def ensure_login_logs_columns(engine) -> None:
    inspector = inspect(engine)
    if "login_logs" not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns("login_logs")}
    if "user_email" in existing:
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE login_logs ADD COLUMN user_email VARCHAR(100)"))
