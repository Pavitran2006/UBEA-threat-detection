import os
import datetime
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List

# Security Config
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "cyber-guard-super-secret-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

class TokenBlacklist:
    _blacklisted = set()

    @classmethod
    def blacklist(cls, token: str):
        cls._blacklisted.add(token)

    @classmethod
    def is_blacklisted(cls, token: str) -> bool:
        return token in cls._blacklisted

class AuthHandler:
    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.datetime.utcnow() + expires_delta
        else:
            expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire, "tenant_id": data.get("tenant_id", "default")})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def create_refresh_token(email: str):
        expire = datetime.datetime.utcnow() + datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode = {"sub": email, "exp": expire, "type": "refresh"}
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def decode_token(token: str):
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    @staticmethod
    def get_current_user(request: Request):
        token = request.cookies.get("access_token")
        if not token:
            # Fallback to Header for non-browser clients
            auth = request.headers.get("Authorization")
            if auth and auth.startswith("Bearer "):
                token = auth.split(" ")[1]
            else:
                raise HTTPException(status_code=401, detail="Not authenticated")
        
        if TokenBlacklist.is_blacklisted(token):
            raise HTTPException(status_code=401, detail="Session terminated due to high risk")

        payload = AuthHandler.decode_token(token)
        if not payload or "tenant_id" not in payload:
             raise HTTPException(status_code=401, detail="Invalid tenant context")
        return payload

def role_required(allowed_roles: List[str]):
    async def role_checker(user: dict = Security(AuthHandler.get_current_user)):
        if user.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail="Operation not permitted for your role")
        return user
    return role_checker
