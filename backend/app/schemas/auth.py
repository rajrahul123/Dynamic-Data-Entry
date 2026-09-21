"""Pydantic schemas for authentication."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.user import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    USERNAME_PATTERN,
)


class LoginRequest(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=255,
        description="Username or email address.",
    )
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(
        pattern=USERNAME_PATTERN,
        description="Unique username, 3-50 chars: letters, digits, . _ -",
    )
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    full_name: str | None = Field(default=None, max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class ChangePasswordResponse(BaseModel):
    detail: str = "Password updated successfully"


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=4096)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class GenericAuthResponse(BaseModel):
    """Uniform message body used by public auth endpoints."""

    detail: str