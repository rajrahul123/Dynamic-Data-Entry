"""Pydantic schemas for user management.

Public schemas never expose ``password_hash`` or any other secret.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import Role

USERNAME_PATTERN = r"^[a-zA-Z0-9_.-]{3,50}$"
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


class UserCreate(BaseModel):
    username: str = Field(
        pattern=USERNAME_PATTERN,
        description="Unique username, 3-50 chars: letters, digits, . _ -",
    )
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    full_name: str | None = Field(default=None, max_length=100)
    role: Role = Role.viewer


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=100)
    password: str | None = Field(
        default=None, min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )
    role: Role | None = None
    is_active: bool | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    full_name: str | None
    role: Role
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None