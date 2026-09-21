"""Subscription ORM model.

A subscription record belongs to a tenant (the billing unit) and records who
subscribed, which plan they are on, whether it is active, when it expires, and
the payment-provider customer id. During this phase billing is stubbed: the
checkout endpoint returns a placeholder URL and, when
``billing_auto_activate`` is enabled (the default outside production), the
subscription is activated immediately so the full flow can be exercised
without a payment provider.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class PlanType(str, Enum):
    free = "free"
    monthly = "monthly"
    yearly = "yearly"


class SubscriptionStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    expired = "expired"
    canceled = "canceled"


class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    plan_type: Mapped[PlanType] = mapped_column(
        SAEnum(PlanType, name="plan_type", native_enum=False, length=20),
        nullable=False,
        default=PlanType.free,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus, name="subscription_status", native_enum=False, length=20),
        nullable=False,
        default=SubscriptionStatus.inactive,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provider_customer_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    tenant: Mapped["Tenant"] = relationship()
    user: Mapped["User"] = relationship()