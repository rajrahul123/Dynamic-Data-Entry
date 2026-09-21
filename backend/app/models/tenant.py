"""Tenant (organization) ORM model.

Every authenticated user belongs to exactly one tenant. All business data
(``Form``, ``FormField``, ``Submission``, and the other users of the
organization) is scoped to the same tenant, which is what gives every signup a
hard data-isolation boundary: queries are automatically rewritten to include
``tenant_id`` whenever a tenant context is active (see ``app.core.tenancy``).
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="tenant")
    forms: Mapped[list["Form"]] = relationship(back_populates="tenant")