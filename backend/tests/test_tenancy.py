"""Cross-tenant data isolation tests.

Every self-signup (and every ``create_user`` without an explicit tenant)
lands in its own organization. These tests verify that neither reads nor
writes can cross that boundary: one tenant's forms, users, and records are
completely invisible (404 / empty list) to another tenant, even when both
tenants hold elevated roles.
"""

from sqlalchemy import select

from app.models import Role, Submission, Tenant, User

from .conftest import create_user, login_headers

ADMIN_PASSWORD = "secret123"


def _make_tenant(db_session, name) -> Tenant:
    tenant = Tenant(name=name)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _publish_form(client, headers, name="Isolated Form", fields=None):
    response = client.post("/api/forms", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    form_id = response.json()["id"]
    for field in fields or []:
        result = client.post(f"/api/forms/{form_id}/fields", headers=headers, json=field)
        assert result.status_code == 201, result.text
    result = client.post(f"/api/forms/{form_id}/publish", headers=headers)
    assert result.status_code == 200, result.text
    return form_id


LOCKED_FIELDS = [
    {"field_key": "name", "label": "Name", "field_type": "text"},
]


class TestTenantIsolation:
    def test_admin_cannot_see_other_tenants_forms(self, client, db_session):
        tenant_a = _make_tenant(db_session, "Tenant A")
        tenant_b = _make_tenant(db_session, "Tenant B")
        create_user(db_session, "admin_a", "admin_a@example.com", password=ADMIN_PASSWORD, role=Role.admin, tenant=tenant_a)
        create_user(db_session, "admin_b", "admin_b@example.com", password=ADMIN_PASSWORD, role=Role.admin, tenant=tenant_b)
        headers_a = login_headers(client, "admin_a", ADMIN_PASSWORD)
        headers_b = login_headers(client, "admin_b", ADMIN_PASSWORD)

        form_id = _publish_form(client, headers_a, fields=LOCKED_FIELDS)

        listing = client.get("/api/forms", headers=headers_b)
        assert listing.status_code == 200
        assert form_id not in [form["id"] for form in listing.json()]

        detail = client.get(f"/api/forms/{form_id}", headers=headers_b)
        assert detail.status_code == 404

        definition = client.get(f"/api/forms/{form_id}/definition", headers=headers_b)
        assert definition.status_code == 404

    def test_admin_cannot_list_other_tenants_users(self, client, db_session):
        tenant_a = _make_tenant(db_session, "Tenant A")
        tenant_b = _make_tenant(db_session, "Tenant B")
        create_user(db_session, "admin_a", "admin_a@example.com", password=ADMIN_PASSWORD, role=Role.admin, tenant=tenant_a)
        create_user(db_session, "local", "local@example.com", tenant=tenant_a)
        create_user(db_session, "admin_b", "admin_b@example.com", password=ADMIN_PASSWORD, role=Role.admin, tenant=tenant_b)
        headers_a = login_headers(client, "admin_a", ADMIN_PASSWORD)
        headers_b = login_headers(client, "admin_b", ADMIN_PASSWORD)

        usernames_a = [u["username"] for u in client.get("/api/users", headers=headers_a).json()]
        assert "local" in usernames_a
        assert "admin_b" not in usernames_a

        usernames_b = [u["username"] for u in client.get("/api/users", headers=headers_b).json()]
        assert "local" not in usernames_b
        assert "admin_b" in usernames_b

    def test_records_are_invisible_across_tenants(self, client, db_session):
        admin_user_a = create_user(
            db_session, "admin_a", "admin_a@example.com", password=ADMIN_PASSWORD, role=Role.admin
        )
        headers_a = login_headers(client, "admin_a", ADMIN_PASSWORD)
        tenant_b = _make_tenant(db_session, "Tenant B")
        admin_b = create_user(
            db_session, "admin_b", "admin_b@example.com", password=ADMIN_PASSWORD,
            role=Role.admin, tenant=tenant_b,
        )
        headers_b = login_headers(client, "admin_b", ADMIN_PASSWORD)

        form_id = _publish_form(client, headers_a, fields=LOCKED_FIELDS)
        created = client.post(
            f"/api/forms/{form_id}/submissions",
            headers=headers_a,
            json={"data": {"name": "secret"}},
        )
        assert created.status_code == 201, created.text

        # B cannot see A's records, the count, or the records listing page.
        listing = client.get(f"/api/forms/{form_id}/submissions", headers=headers_b)
        assert listing.status_code == 404

        available_b = client.get("/api/records/forms", headers=headers_b).json()
        assert form_id not in [form["id"] for form in available_b]

        # A still sees its own record.
        listing_a = client.get(f"/api/forms/{form_id}/submissions", headers=headers_a)
        assert listing_a.status_code == 200
        assert listing_a.json()["total"] == 1

        all_submissions = db_session.scalars(select(Submission)).all()
        assert all(s.tenant_id == admin_user_a.tenant_id for s in all_submissions)
        assert admin_b.tenant_id not in {s.tenant_id for s in all_submissions}

    def test_operator_cannot_write_into_other_tenant(self, client, db_session):
        tenant_b = _make_tenant(db_session, "Tenant B")
        create_user(db_session, "admin_a", "admin_a@example.com", password=ADMIN_PASSWORD, role=Role.admin)
        headers_a = login_headers(client, "admin_a", ADMIN_PASSWORD)
        create_user(
            db_session, "op_b", "op_b@example.com", password=ADMIN_PASSWORD,
            role=Role.operator, tenant=tenant_b,
        )
        headers_b = login_headers(client, "op_b", ADMIN_PASSWORD)

        form_id = _publish_form(client, headers_a, fields=LOCKED_FIELDS)

        attempt = client.post(
            f"/api/forms/{form_id}/submissions",
            headers=headers_b,
            json={"data": {"name": "intrusion"}},
        )
        assert attempt.status_code == 404

        rename = client.patch(f"/api/forms/{form_id}", headers=headers_b, json={"name": "Hijacked"})
        assert rename.status_code in (403, 404)

    def test_registered_user_isolated_from_other_registrants(self, client, db_session):
        first = client.post(
            "/api/auth/register",
            json={"username": "first", "email": "first@example.com", "password": "passw0rd!x"},
        )
        second = client.post(
            "/api/auth/register",
            json={"username": "second", "email": "second@example.com", "password": "passw0rd!x"},
        )
        assert first.status_code == 201
        assert second.status_code == 201

        first_headers = login_headers(client, "first", "passw0rd!x")
        second_headers = login_headers(client, "second", "passw0rd!x")

        users_first = client.get("/api/users", headers=first_headers)
        assert users_first.status_code == 200  # registrants administer their own tenant
        assert [u["username"] for u in users_first.json()] == ["first"]

        users_second = client.get("/api/users", headers=second_headers)
        assert [u["username"] for u in users_second.json()] == ["second"]

        records_first = client.get("/api/records/forms", headers=first_headers).json()
        records_second = client.get("/api/records/forms", headers=second_headers).json()
        assert records_first == []
        assert records_second == []

        users = db_session.scalars(select(User)).all()
        tenants = {user.tenant_id for user in users}
        assert len(tenants) == 2