"""Reusable FastAPI dependencies for authentication and authorization.

These are the real security boundary. Frontend role checks are UX only.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.tenancy import bind_tenant
from app.models import PlanType, Role, Subscription, SubscriptionStatus, User

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    db: DbSession,
) -> User:
    """Resolve the authenticated user from a valid bearer token."""
    if credentials is None:
        raise _unauthorized()

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise _unauthorized()

    subject = payload.get("sub")
    if subject is None:
        raise _unauthorized()

    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        raise _unauthorized()

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized()

    # Bind the session to the user's tenant *after* the unscoped lookup above,
    # so every subsequent ORM query on this session is tenant-filtered.
    bind_tenant(db, user.tenant_id)

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def _payment_required() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail="An active paid subscription is required for this action",
    )


def _as_utc(value: datetime) -> datetime:
    """Return a UTC-aware copy of ``value`` (SQLite stores naive datetimes)."""
    if value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def require_active_subscription(
    user: CurrentUser,
    db: DbSession,
) -> User:
    """Only tenants with an active paid subscription.

    The subscription is the tenant's billing record, so a single active paid
    plan protects every user in the organization (the free plan and timed-out
    plans do not satisfy this gate). The current plan is the most recent
    subscription row for the tenant.
    """
    now = datetime.now(timezone.utc)
    subscription = db.scalar(
        select(Subscription)
        .where(Subscription.tenant_id == user.tenant_id)
        .order_by(Subscription.id.desc())
        .limit(1)
    )

    if (
        subscription is None
        or subscription.plan_type is PlanType.free
        or subscription.status is not SubscriptionStatus.active
        or subscription.expires_at is not None
        and _as_utc(subscription.expires_at) <= now
    ):
        raise _payment_required()

    return user


ActiveSubscription = Annotated[User, Depends(require_active_subscription)]


def _forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions",
    )


def require_admin(user: CurrentUser) -> User:
    """Only administrators."""
    if user.role is not Role.admin:
        raise _forbidden()
    return user


def require_operator(user: CurrentUser) -> User:
    """Administrators and operators."""
    if user.role not in (Role.admin, Role.operator):
        raise _forbidden()
    return user


def require_viewer(user: CurrentUser) -> User:
    """Any authenticated, active user."""
    return user


CurrentAdmin = Annotated[User, Depends(require_admin)]
CurrentOperator = Annotated[User, Depends(require_operator)]