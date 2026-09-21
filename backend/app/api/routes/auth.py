"""Authentication endpoints: register, login, and current user.

Public registration always creates an ``admin`` account: every self-signup
provisions its own organization (``Tenant``), and the founder of that
organization is its administrator so they can build forms, submit entries,
export data)Skip and manage their team. The role is never taken from the
request body: only administrators can assign elevated roles via the user
management API.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.email import send_password_reset_otp_email
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    generate_reset_otp,
    hash_password,
    verify_password,
)
from app.models import PlanType, Role, Subscription, SubscriptionStatus, Tenant, User
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
    """Create a self-registered account and provision its own organization.

    Public registration always creates an ``admin`` account: the registrant
    becomes the administrator of the ``Tenant`` that is provisioned for them
    (with a free plan), so from the first login they can build forms, run data
    entry, export, and invite their own team. The role is never taken from the
    request body; elevating or changing roles for teammates is restricted to
    tenant admins through the user-management endpoint.
    """
    if db.scalar(select(User).where(User.username == payload.username)) is not None:
        raise _conflict("Username is already taken")

    if db.scalar(select(User).where(User.email == payload.email)) is not None:
        raise _conflict("Email is already registered")

    tenant = Tenant(name=f"{payload.full_name or payload.username}'s organization")
    db.add(tenant)
    db.flush()

    user = User(
        username=payload.username,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=Role.admin,
        is_active=True,
        tenant_id=tenant.id,
    )
    db.add(user)
    db.flush()

    db.add(
        Subscription(
            tenant_id=tenant.id,
            user_id=user.id,
            plan_type=PlanType.free,
            status=SubscriptionStatus.active,
        )
    )
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
    """Request a 6-digit password-reset code (OTP) for an email address.

    The response is deliberately identical whether or not the email exists so
    the endpoint cannot be used to enumerate accounts. For an existing account
    a short-lived OTP is stored (argon2-hashed) and emailed; otherwise nothing
    is generated and no mail is sent.
    """
    generic_detail = "If an account exists for that email, a password reset code has been sent."

    user = db.scalar(select(User).where(User.email == str(payload.email)))

    if user is not None:
        otp = generate_reset_otp()
        user.reset_otp_hash = hash_password(otp)
        user.reset_otp_expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=_settings.password_reset_otp_expire_minutes
        )
        db.add(user)
        db.commit()
        send_password_reset_otp_email(str(user.email), otp)

    return GenericAuthResponse(detail=generic_detail)


@router.post("/reset-password", response_model=GenericAuthResponse)
@limiter.limit(_settings.auth_reset_password_rate_limit)
def reset_password(
    request: Request, response: Response, payload: ResetPasswordRequest, db: DbSession
) -> GenericAuthResponse:
    """Set a new password using a valid, unexpired 6-digit OTP.

    The OTP is verified against the argon2 hash stored on the user's row when
    the code was requested and must still be within its expiry window. On
    success the OTP is consumed (single-use). Unknown emails, wrong codes,
    expired codes, and missing stored codes all return the same message so the
    endpoint leaks nothing about which accounts exist.
    """
    invalid_otp_message = "The reset code is invalid or has expired"

    user = db.scalar(select(User).where(User.email == str(payload.email)))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=invalid_otp_message
        )

    if user.reset_otp_hash is None or user.reset_otp_expires_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=invalid_otp_message
        )

    if not verify_password(payload.otp, user.reset_otp_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=invalid_otp_message
        )

    expires_at = user.reset_otp_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=invalid_otp_message
        )

    user.password_hash = hash_password(payload.new_password)
    user.reset_otp_hash = None
    user.reset_otp_expires_at = None
    db.add(user)
    db.commit()

    return GenericAuthResponse(detail="Your password has been reset successfully")