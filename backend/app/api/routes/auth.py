"""Authentication endpoints: login and current user."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import or_, select

from app.api.deps import CurrentUser, DbSession
from app.core.security import create_access_token, verify_password
from app.models import User
from app.schemas import LoginRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


def _invalid_credentials() -> HTTPException:
    # Uniform message: do not reveal whether the user exists or is disabled.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username/email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    user = db.scalar(
        select(User).where(
            or_(User.username == payload.username, User.email == payload.username)
        )
    )

    if user is None or not verify_password(payload.password, user.password_hash):
        raise _invalid_credentials()

    if not user.is_active:
        raise _invalid_credentials()

    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()

    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> User:
    """Return the currently authenticated user."""
    return user