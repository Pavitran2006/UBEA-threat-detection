from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User
from ..security import get_current_user

router = APIRouter()


@router.post("/disable-user/{user_id}")
async def disable_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user:
        target_user.status = "disabled"
        target_user.is_active = False
        db.commit()

    return {"status": "disabled"}


@router.post("/enable-user/{user_id}")
async def enable_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user:
        target_user.status = "active"
        target_user.is_active = True
        db.commit()

    return {"status": "enabled"}


@router.post("/api/admin/users/{user_id}/disable")
async def api_disable_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user:
        target_user.status = "disabled"
        target_user.is_active = False
        db.commit()
    return {"status": "disabled"}


@router.post("/api/admin/users/{user_id}/enable")
async def api_enable_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user:
        target_user.status = "active"
        target_user.is_active = True
        db.commit()
    return {"status": "enabled"}
