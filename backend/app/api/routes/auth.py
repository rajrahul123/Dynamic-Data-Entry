"""Authentication endpoints: register, login, and current user.

Public registration always creates a Viewer account. The role is never taken
from the request body: only administrators can assign elevated roles.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response, status
from jwt import InvalidTokenError
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.email import send_password_reset_email
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    decode_password_reset_token,
    hash_password,
    verify_password,
)
from app.models import Role, User
from app.schemas import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    ForgotPasswordRequest,
    GenericAuthResponse,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserRead,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_settings = get_settings()


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
@limiter.limit(_settings.auth_register_rate_limit)
def register(
    request: Request, response: Response, payload: RegisterRequest, db: DbSession
) -> User:
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
@limiter.limit(_settings.auth_login_rate_limit)
def login(
    request: Request, response: Response, payload: LoginRequest, db: DbSession
) -> TokenResponse:
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


@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password(
    payload: ChangePasswordRequest,
    db: DbSession,
    user: CurrentUser,
) -> ChangePasswordResponse:
    """Let an authenticated user replace their own password.

    The current password is verified with the stored argon2 hash before the
    new one is applied; a wrong current password is rejected with a uniform
    400 so the existing credentials are never disclosed as correct/incorrect
    in a way that helps an attacker.
    """
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password",
        )

    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return ChangePasswordResponse()


@router.post("/forgot-password", response_model=GenericAuthResponse)
@limiter.limit(_settings.auth_forgot_password_rate_limit)
def forgot_password(
    request: Request, response: Response, payload: ForgotPasswordRequest, db: DbSession
) -> GenericAuthResponse:
    """Request a password-reset link for an email address.

    The response is deliberately identical whether or not the email exists so
    the endpoint cannot be used to enumerate accounts. When SMTP is
    configured a reset link is emailed; otherwise (development only) the link
    is written to the application log instead.
    """
    generic_detail = "If an account exists for that email, a password reset link has been sent."

    user = db.scalar(select(User).where(User.email == str(payload.email)))

    if user is not None:
        token = create_password_reset_token(str(user.id))
        reset_link = f"{_settings.frontend_base_url}/reset-password?token={token}"
        send_password_reset_email(str(user.email), reset_link)

    return GenericAuthResponse(detail=generic_detail)


@router.post("/reset-password", response_model=GenericAuthResponse)
def reset_password(
    payload: ResetPasswordRequest, db: DbSession
) -> GenericAuthResponse:
    """Set a new password using a valid, unexpired reset token.

    The token is a short-lived JWT carrying the user id; both its signature
    and its expiration are verified before the password is replaced.
    """
    try:
        claims = decode_password_reset_token(payload.token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The reset token is invalid or has expired",
        )

    subject = claims.get("sub")
    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The reset token is invalid or has expired",
        )

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The reset token is invalid or has expired",
        )

    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()

    return GenericAuthResponse(detail="Your password has been reset successfully")