from datetime import datetime
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.auth import SECRET_KEY, ALGORITHM, TOKEN_COOKIE_NAME, decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)

async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    # Try to get token from cookie first (common for web apps)
    token = request.cookies.get(TOKEN_COOKIE_NAME)
    
    # If not in cookie, try Authorization header
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None
        
    email: str = payload.get("sub")
    if email is None:
        return None
        
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.last_activity = datetime.utcnow()
        db.commit()
    return user

def role_required(*roles: str):
    allowed = {r.lower() for r in roles}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if (current_user.role or "").lower() not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role permissions"
            )
        return current_user

    return dependency

async def get_current_admin_user(request: Request, current_user: User = Depends(get_current_user)) -> User:
    if not current_user:
        # If it's a browser page request, redirect to login instead of showing JSON
        if "text/html" in request.headers.get("Accept", ""):
            from fastapi.responses import RedirectResponse
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                headers={"Location": "/login"}
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return current_user
