"""Admin-only user management endpoints.

All endpoints in this router require an authenticated administrator.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import CurrentAdmin, DbSession, require_admin
from app.core.security import hash_password
from app.models import Role, User
from app.schemas import UserCreate, UserRead, UserUpdate

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_admin)],
)


def _load_user(db: Session, user_id: int) -> User | None:
    return db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.created_by),
            selectinload(User.updated_by),
        )
    )


def _conflict(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


def _ensure_unique(
    db: Session,
    *,
    username: str | None = None,
    email: str | None = None,
    user_id: int | None = None,
) -> None:
    if username is not None:
        row = db.scalar(select(User).where(User.username == username))
        if row is not None and row.id != user_id:
            raise _conflict("Username is already taken")
    if email is not None:
        row = db.scalar(select(User).where(User.email == email))
        if row is not None and row.id != user_id:
            raise _conflict("Email is already registered")


@router.get("", response_model=list[UserRead])
def list_users(
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .options(
                selectinload(User.created_by),
                selectinload(User.updated_by),
            )
            .order_by(User.id)
            .limit(limit)
            .offset(offset)
        )
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DbSession, admin: CurrentAdmin) -> User:
    _ensure_unique(db, username=payload.username, email=str(payload.email))

    user = User(
        username=payload.username,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=True,
        tenant_id=admin.tenant_id,
        created_by_id=admin.id,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict("Username or email is already taken")
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: DbSession) -> User:
    user = _load_user(db, user_id)
    if user is None:
        raise _not_found()
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserUpdate, db: DbSession, admin: CurrentAdmin) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise _not_found()

    changes = payload.model_dump(exclude_unset=True)

    if user.id == admin.id and changes.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An admin cannot deactivate their own account",
        )

    if (
        user.id == admin.id
        and changes.get("role") is not None
        and changes.get("role") is not Role.admin
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An admin cannot change their own role",
        )

    if "email" in changes and changes["email"] is not None:
        changes["email"] = str(changes["email"])
        _ensure_unique(db, email=changes["email"], user_id=user.id)

    if "password" in changes and changes["password"] is not None:
        changes["password_hash"] = hash_password(changes["password"])
    changes.pop("password", None)

    for field, value in changes.items():
        setattr(user, field, value)

    # Record which admin performed the edit for the "last updated by" trail.
    if changes:
        user.updated_by_id = admin.id

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict("Username or email is already taken")
    db.refresh(user)
    return user