"""Password hashing and JWT utilities.

Never store plaintext passwords and never log secrets. All secrets come from
environment settings, never from code.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import get_settings

password_hash = PasswordHash.recommended()

TOKEN_TYPE_FIELD = "type"
ACCESS_TOKEN_TYPE = "access"


def hash_password(password: str) -> str:
    """Hash a plaintext password for storage."""
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    return password_hash.verify(password, hashed_password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token for the given subject (user id)."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload: dict[str, Any] = {
        "sub": subject,
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Raises ``jwt.InvalidTokenError`` for expired, malformed, or invalid tokens.
    """
    settings = get_settings()
    payload = jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    if payload.get(TOKEN_TYPE_FIELD) != ACCESS_TOKEN_TYPE:
        raise InvalidTokenError("Invalid token type")
    return payload