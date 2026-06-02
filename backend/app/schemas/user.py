import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole


class UserOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    full_name: str
    role: UserRole
    is_active: bool
    is_verified: bool
    avatar_url: str | None
    phone: str | None
    organization_id: uuid.UUID | None
    created_at: datetime


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None


class UserList(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    size: int
    pages: int
