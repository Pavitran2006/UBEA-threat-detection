from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict


class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    id: int
    is_verified: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProfileUpdate(BaseModel):
    phone: str | None = None
    username: str | None = None



