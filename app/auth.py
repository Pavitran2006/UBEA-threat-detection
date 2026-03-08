from datetime import datetime, timedelta, timezone
import os
import secrets
import string

from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "fallback-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
RESET_TOKEN_EXPIRE_MINUTES = 15
TOKEN_COOKIE_NAME = "access_token"
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"
REVOKED_TOKENS: set[str] = set()
REVOKED_USERS: set[int] = set()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "token_type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "token_type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        if token in REVOKED_TOKENS:
            return None
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("token_type") != "access":
            return None
        uid = payload.get("uid")
        if isinstance(uid, int) and uid in REVOKED_USERS:
            return None
        return payload
    except JWTError:
        return None


def decode_refresh_token(token: str) -> dict | None:
    try:
        if token in REVOKED_TOKENS:
            return None
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("token_type") != "refresh":
            return None
        uid = payload.get("uid")
        if isinstance(uid, int) and uid in REVOKED_USERS:
            return None
        return payload
    except JWTError:
        return None


def revoke_token(token: str) -> None:
    if token:
        REVOKED_TOKENS.add(token)


def revoke_user(user_id: int) -> None:
    REVOKED_USERS.add(user_id)


# Password Reset Token Generation
def generate_password_reset_token(length: int = 64) -> str:
    """
    Generate a secure random token for password reset.
    
    Advantages:
    - Using secrets module for cryptographically secure random generation
    - 64 character length provides sufficient entropy
    - Mix of letters and digits for token diversity
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def get_password_reset_token_expiry() -> datetime:
    """
    Calculate expiry time for password reset token (15 minutes).
    
    Advantages:
    - Short expiry prevents token abuse
    - Uses UTC timezone for consistency across systems
    """
    return datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
