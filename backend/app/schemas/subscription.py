"""Pydantic schemas for subscriptions and billing.

Subscription reads are scoped to the caller's tenant (the billing unit), so a
single active plan protects every user in an organization.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import PlanType, SubscriptionStatus


class PlanRead(BaseModel):
    """Public, static description of a sellable plan."""

    key: PlanType
    name: str
    description: str
    price_usd: int


class SubscriptionRead(BaseModel):
    """The tenant's current subscription as the frontend needs it."""

    model_config = ConfigDict(from_attributes=True)

    plan_type: PlanType
    status: SubscriptionStatus
    expires_at: datetime | None
    provider_customer_id: str | None


class CheckoutRequest(BaseModel):
    plan: PlanType = Field(description="Plan the tenant wants to subscribe to")


class CheckoutResponse(BaseModel):
    """Result of a (stubbed) checkout request."""

    checkout_url: str | None = Field(
        default=None,
        description=(
            "Placeholder billing URL when checkout is not auto-activated; "
            "None when the plan was activated locally."
        ),
    )
    subscription: SubscriptionRead