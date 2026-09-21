"""Subscription and billing endpoints.

A subscription is a tenant-level billing record: one active paid plan covers
every user in the organization. ``GET /api/subscription`` and
``POST /api/subscription/checkout`` require an authenticated user; the plans
catalog under ``/api/billing`` is public so the landing page can render
pricing without authentication.

Checkout is intentionally stubbed until a payment provider is wired up:

* With ``billing_auto_activate`` enabled (the development default) the picked
  plan is activated immediately and ``checkout_url`` is ``None``.
* With it disabled (production) a placeholder billing URL is returned and no
  subscription row changes until a future webhook confirms payment.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentAdmin, CurrentUser, DbSession
from app.core.config import get_settings
from app.models import PlanType, Subscription, SubscriptionStatus
from app.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    PlanRead,
    SubscriptionRead,
)

router = APIRouter(prefix="/subscription", tags=["subscription"])
billing_router = APIRouter(prefix="/billing", tags=["billing"])

_settings = get_settings()

PLANS: list[PlanRead] = [
    PlanRead(
        key=PlanType.free,
        name="Free",
        description="Up to 3 forms, community support, unlimited view-only access.",
        price_usd=0,
    ),
    PlanRead(
        key=PlanType.monthly,
        name="Monthly",
        description="Unlimited forms, records and exports for a single workspace.",
        price_usd=19,
    ),
    PlanRead(
        key=PlanType.yearly,
        name="Yearly",
        description="Everything in Monthly at two months free per year.",
        price_usd=190,
    ),
]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="No subscription found"
    )


def _latest_subscription(db: DbSession, tenant_id: int) -> Subscription | None:
    subscriptions = list(
        db.query(Subscription)
        .filter(Subscription.tenant_id == tenant_id)
        .order_by(Subscription.id.desc())
        .limit(1)
    )
    return subscriptions[0] if subscriptions else None


@router.get("", response_model=SubscriptionRead)
def get_subscription(user: CurrentUser, db: DbSession) -> Subscription:
    """Return the authenticated user's organization subscription."""
    subscription = _latest_subscription(db, user.tenant_id)
    if subscription is None:
        raise _not_found()
    return subscription


def _auto_activate_subscription(
    db: DbSession,
    *,
    tenant_id: int,
    user_id: int,
    plan: PlanType,
) -> Subscription:
    """Create/store an active subscription row for the tenant.

    A subscription is the tenant's billing record, so each checkout replaces
    the previous row (history could be retained later; a single current row
    keeps ``require_active_subscription`` trivially correct).
    """
    duration = {
        PlanType.monthly: timedelta(days=30),
        PlanType.yearly: timedelta(days=365),
    }.get(plan)

    current = _latest_subscription(db, tenant_id)
    if (
        current is not None
        and current.plan_type is plan
        and current.status is SubscriptionStatus.active
    ):
        return current

    subscription = Subscription(
        tenant_id=tenant_id,
        user_id=user_id,
        plan_type=plan,
        status=SubscriptionStatus.active,
        expires_at=(datetime.now(timezone.utc) + duration) if duration else None,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def _placeholder_response(plan: PlanType) -> CheckoutResponse:
    return CheckoutResponse(
        checkout_url=f"/billing/checkout?plan={plan.value}",
        subscription=SubscriptionRead(
            plan_type=plan,
            status=SubscriptionStatus.inactive,
            expires_at=None,
            provider_customer_id=None,
        ),
    )


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(
    payload: CheckoutRequest,
    admin: CurrentAdmin,
    db: DbSession,
) -> CheckoutResponse:
    """Request a subscription to a plan (admin only — billing action).

    With ``billing_auto_activate`` the plan is applied to the organization
    immediately; otherwise a placeholder payment URL is returned and nothing is
    persisted (a future provider webhook would confirm payment).
    """
    if not _settings.billing_auto_activate:
        return _placeholder_response(payload.plan)

    subscription = _auto_activate_subscription(
        db,
        tenant_id=admin.tenant_id,
        user_id=admin.id,
        plan=payload.plan,
    )
    return CheckoutResponse(
        checkout_url=None,
        subscription=SubscriptionRead.model_validate(subscription),
    )


@billing_router.get("/plans", response_model=list[PlanRead])
def list_plans() -> list[PlanRead]:
    """Public list of the sellable plans (no authentication)."""
    return PLANS