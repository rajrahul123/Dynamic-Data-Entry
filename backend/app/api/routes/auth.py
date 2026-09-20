"""Authentication endpoints: register, login, and current user.

Public registration always creates a Viewer account. The role is never taken
from the request body: only administrators can assign elevated roles.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Role, User
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


def _conflict(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def _invalid_credentials() -> HTTPException:
    # Uniform message: do not reveal whether the user exists or is disabled.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username/email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession) -> User:
    """Create a public account with the Viewer role.

    The role is always ``Role.viewer``; a role (or any other field) sent by the
    client is rejected outright by the schema, preventing privilege escalation.
    """
    if db.scalar(select(User).where(User.username == payload.username)) is not None:
        raise _conflict("Username is already taken")

    if db.scalar(select(User).where(User.email == payload.email)) is not None:
        raise _conflict("Email is already registered")

    user = User(
        username=payload.username,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=Role.viewer,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict("Username or email is already taken")
    db.refresh(user)
    return user


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