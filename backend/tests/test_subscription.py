"""Subscription gating and billing endpoint tests.

``require_active_subscription`` protects Form Builder, Data Entry, and Export
writes. The gate is tenant-wide: one active paid plan protects every user in
the organization, while free / expired / missing plans are rejected with 402.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import PlanType, Role, Subscription, SubscriptionStatus, Tenant

from .conftest import create_user, login_headers

ADMIN_PASSWORD = "secret123"


def _create_form(client, headers):
    response = client.post("/api/forms", headers=headers, json={"name": "Gated Form"})
    return response


def _free_user(client, db_session):
    create_user(db_session, "freeuser", "free@example.com", password=ADMIN_PASSWORD, role=Role.admin, plan=PlanType.free)
    return login_headers(client, "freeuser", ADMIN_PASSWORD)


class TestFreePlanBlocksWrites:
    def test_form_builder_blocked(self, client, db_session):
        headers = _free_user(client, db_session)

        response = _create_form(client, headers)

        assert response.status_code == 402

    def test_data_entry_blocked(self, client, db_session):
        tenant = Tenant(name="Paid Tenant")
        db_session.add(tenant)
        db_session.commit()
        admin = create_user(db_session, "paid", "paid@example.com", password=ADMIN_PASSWORD, role=Role.admin, tenant=tenant)
        headers = login_headers(client, "paid", ADMIN_PASSWORD)

        form_response = client.post("/api/forms", headers=headers, json={"name": "Paid Form"})
        assert form_response.status_code == 201
        form_id = form_response.json()["id"]
        assert client.post(f"/api/forms/{form_id}/fields", headers=headers, json={
            "field_key": "name", "label": "Name", "field_type": "text"
        }).status_code == 201
        assert client.post(f"/api/forms/{form_id}/publish", headers=headers).status_code == 200

        free_user = create_user(
            db_session, "freeop", "freeop@example.com", password=ADMIN_PASSWORD,
            role=Role.operator, plan=PlanType.free,
        )
        free_headers = login_headers(client, "freeop", ADMIN_PASSWORD)

        response = client.post(
            f"/api/forms/{form_id}/submissions",
            headers=free_headers,
            json={"data": {"name": "x"}},
        )
        assert response.status_code == 402
        _ = admin

    def test_export_blocked(self, client, db_session):
        tenant = Tenant(name="Paid Tenant")
        db_session.add(tenant)
        db_session.commit()
        create_user(db_session, "paid", "paid@example.com", password=ADMIN_PASSWORD, role=Role.admin, tenant=tenant)
        headers = login_headers(client, "paid", ADMIN_PASSWORD)

        form_id = client.post("/api/forms", headers=headers, json={"name": "Paid Form"}).json()["id"]
        assert client.post(f"/api/forms/{form_id}/fields", headers=headers, json={
            "field_key": "name", "label": "Name", "field_type": "text"
        }).status_code == 201
        assert client.post(f"/api/forms/{form_id}/publish", headers=headers).status_code == 200

        create_user(db_session, "freeview", "freeview@example.com", password=ADMIN_PASSWORD, plan=PlanType.free)
        free_headers = login_headers(client, "freeview", ADMIN_PASSWORD)

        response = client.get(f"/api/forms/{form_id}/submissions/export", headers=free_headers, params={"format": "csv"})
        assert response.status_code == 402


class TestPaidPlanAllowsWrites:
    def test_active_monthly_plan_passes_gate(self, client, db_session):
        create_user(db_session, "admin", "admin@example.com", password=ADMIN_PASSWORD, role=Role.admin, plan=PlanType.monthly)
        headers = login_headers(client, "admin", ADMIN_PASSWORD)

        response = _create_form(client, headers)
        assert response.status_code == 201
        assert response.json()["name"] == "Gated Form"

    def test_tenant_wide_gating(self, client, db_session):
        """A paid subscription covers every member of the tenant."""
        create_user(db_session, "admin", "admin@example.com", password=ADMIN_PASSWORD, role=Role.admin, plan=PlanType.monthly)
        create_user(db_session, "operator", "operator@example.com", password=ADMIN_PASSWORD, role=Role.operator)
        headers = login_headers(client, "operator", ADMIN_PASSWORD)

        response = _create_form(client, headers)
        assert response.status_code == 403  # operator is not an admin, but NOT 402


class TestExpiredAndMissingPlans:
    def test_expired_subscription_blocks_writes(self, client, db_session):
        admin = create_user(db_session, "admin", "admin@example.com", password=ADMIN_PASSWORD, role=Role.admin, plan=PlanType.monthly)
        subscription = db_session.scalar(
            select(Subscription).where(Subscription.tenant_id == admin.tenant_id)
        )
        subscription.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db_session.add(subscription)
        db_session.commit()

        headers = login_headers(client, "admin", ADMIN_PASSWORD)
        response = _create_form(client, headers)
        assert response.status_code == 402

    def test_no_subscription_blocks_writes(self, client, db_session):
        create_user(db_session, "admin", "admin@example.com", password=ADMIN_PASSWORD, role=Role.admin, plan=None)
        headers = login_headers(client, "admin", ADMIN_PASSWORD)

        response = _create_form(client, headers)
        assert response.status_code == 402

    def test_inactive_status_blocks_writes(self, client, db_session):
        admin = create_user(db_session, "admin", "admin@example.com", password=ADMIN_PASSWORD, role=Role.admin, plan=PlanType.monthly)
        subscription = db_session.scalar(
            select(Subscription).where(Subscription.tenant_id == admin.tenant_id)
        )
        subscription.status = SubscriptionStatus.inactive
        db_session.add(subscription)
        db_session.commit()

        headers = login_headers(client, "admin", ADMIN_PASSWORD)
        response = _create_form(client, headers)
        assert response.status_code == 402


class TestSubscriptionEndpoints:
    def test_get_subscription_returns_plan(self, client, db_session):
        create_user(db_session, "admin", "admin@example.com", password=ADMIN_PASSWORD, role=Role.admin, plan=PlanType.monthly)
        headers = login_headers(client, "admin", ADMIN_PASSWORD)

        response = client.get("/api/subscription", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["plan_type"] == "monthly"
        assert body["status"] == "active"
        assert body["expires_at"] is not None

    def test_plans_catalog_is_public(self, client):
        response = client.get("/api/billing/plans")
        assert response.status_code == 200
        plans = {plan["key"] for plan in response.json()}
        assert {"free", "monthly", "yearly"} <= plans

    def test_checkout_upgrades_free_tenant(self, client, db_session):
        create_user(db_session, "admin", "admin@example.com", password=ADMIN_PASSWORD, role=Role.admin, plan=PlanType.free)
        headers = login_headers(client, "admin", ADMIN_PASSWORD)

        assert _create_form(client, headers).status_code == 402

        response = client.post("/api/subscription/checkout", headers=headers, json={"plan": "monthly"})
        assert response.status_code == 200
        assert response.json()["checkout_url"] is None
        assert response.json()["subscription"]["plan_type"] == "monthly"

        assert _create_form(client, headers).status_code == 201

    def test_checkout_requires_admin(self, client, db_session):
        create_user(db_session, "viewer", "viewer@example.com", password=ADMIN_PASSWORD, plan=PlanType.free)
        headers = login_headers(client, "viewer", ADMIN_PASSWORD)

        response = client.post("/api/subscription/checkout", headers=headers, json={"plan": "monthly"})
        assert response.status_code == 403

    def test_checkout_disabled_returns_placeholder_url(self, client, db_session, monkeypatch):
        create_user(db_session, "admin", "admin@example.com", password=ADMIN_PASSWORD, role=Role.admin, plan=PlanType.free)
        headers = login_headers(client, "admin", ADMIN_PASSWORD)

        from app.api.routes.subscriptions import _settings

        monkeypatch.setattr(_settings, "billing_auto_activate", False)

        response = client.post("/api/subscription/checkout", headers=headers, json={"plan": "monthly"})
        assert response.status_code == 200
        assert response.json()["checkout_url"] is not None
        assert "monthly" in response.json()["checkout_url"]