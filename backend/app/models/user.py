"""User ORM model."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.role import Role


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[Role] = mapped_column(
        SAEnum(Role, name="user_role", native_enum=False, length=20),
        nullable=False,
        default=Role.viewer,
        server_default=Role.viewer.value,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Self-referential admin tracking. `created_by` / `updated_by` resolve the
    # admin who created / last edited this account; the back-populated
    # collections are used only by the ORM to keep both sides consistent.
    created_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys="User.created_by_id",
        remote_side="User.id",
        back_populates="created_users",
    )
    updated_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys="User.updated_by_id",
        remote_side="User.id",
        back_populates="updated_users",
    )
    created_users: Mapped[list["User"]] = relationship(
        "User",
        foreign_keys="User.created_by_id",
        back_populates="created_by",
        passive_deletes=True,
    )
    updated_users: Mapped[list["User"]] = relationship(
        "User",
        foreign_keys="User.updated_by_id",
        back_populates="updated_by",
        passive_deletes=True,
    )

    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="submitted_by_user", passive_deletes=True
    )