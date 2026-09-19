"""Reusable FastAPI dependencies for authentication and authorization.

These are the real security boundary. Frontend role checks are UX only.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import Role, User

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

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


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