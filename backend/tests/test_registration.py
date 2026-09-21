"""Public registration endpoint tests.

Covers account creation, Viewer role enforcement, password security,
duplicate handling, and the requirement that public registration can never
elevate privileges.
"""

from sqlalchemy import select

from app.models import Role, User

from .conftest import create_user, login_headers

VALID = {
    "username": "newbie",
    "email": "newbie@example.com",
    "password": "passw0rd!x",
    "full_name": "Newbie User",
}


def _register(client, **overrides):
    payload = {**VALID, **overrides}
    return client.post("/api/auth/register", json=payload)


class TestRegister:
    def test_successful_registration(self, client, db_session):
        response = _register(client)

        assert response.status_code == 201
        body = response.json()
        assert body["username"] == "newbie"
        assert body["email"] == "newbie@example.com"
        assert body["full_name"] == "Newbie User"
        assert body["is_active"] is True
        assert "password_hash" not in body
        assert "password" not in body

    def test_registered_user_gets_admin_role(self, client, db_session):
        _register(client)

        user = db_session.scalar(select(User).where(User.username == "newbie"))
        assert user is not None
        assert user.role is Role.admin

    def test_password_is_stored_hashed(self, client, db_session):
        _register(client)

        user = db_session.scalar(select(User).where(User.username == "newbie"))
        assert user is not None
        assert user.password_hash != "passw0rd!x"
        assert user.password_hash.startswith("$argon2")

    def test_plaintext_password_never_returned(self, client):
        response = _register(client)

        raw = response.text
        assert "password_hash" not in raw
        assert "passw0rd!x" not in raw

    def test_duplicate_username_rejected(self, client, db_session):
        create_user(db_session, "newbie", "other@example.com")

        response = _register(client)
        assert response.status_code == 409
        assert response.json()["detail"] == "Username is already taken"

        count = db_session.scalar(select(User).where(User.username == "newbie"))
        assert count is not None and count.email == "other@example.com"

    def test_duplicate_email_rejected(self, client, db_session):
        create_user(db_session, "owner", "newbie@example.com")

        response = _register(client)
        assert response.status_code == 409
        assert response.json()["detail"] == "Email is already registered"

        count = db_session.scalar(select(User).where(User.email == "newbie@example.com"))
        assert count is not None and count.username == "owner"

    def test_invalid_username_rejected(self, client, db_session):
        response = _register(client, username="ab")

        assert response.status_code == 422
        assert db_session.scalar(select(User).where(User.email == "newbie@example.com")) is None

    def test_invalid_email_rejected(self, client, db_session):
        response = _register(client, email="not-an-email")

        assert response.status_code == 422
        assert db_session.scalar(select(User).where(User.username == "newbie")) is None

    def test_short_password_rejected(self, client, db_session):
        response = _register(client, password="short")

        assert response.status_code == 422
        assert db_session.scalar(select(User).where(User.username == "newbie")) is None

    def test_missing_required_fields_rejected(self, client, db_session):
        response = client.post("/api/auth/register", json={"username": "nofields"})

        assert response.status_code == 422
        assert db_session.scalar(select(User).where(User.username == "nofields")) is None

    def test_role_admin_from_client_rejected(self, client, db_session):
        response = _register(client, role="admin")

        assert response.status_code == 422
        assert db_session.scalar(select(User).where(User.username == "newbie")) is None

    def test_role_operator_from_client_rejected(self, client, db_session):
        response = _register(client, role="operator")

        assert response.status_code == 422
        assert db_session.scalar(select(User).where(User.username == "newbie")) is None

    def test_anonymous_user_can_register(self, client, db_session):
        response = client.post("/api/auth/register", json=VALID)

        assert response.status_code == 201
        assert db_session.scalar(select(User).where(User.username == "newbie")) is not None


class TestRegisteredUserFlow:
    def test_registered_viewer_can_login(self, client, db_session):
        _register(client)

        response = client.post(
            "/api/auth/login",
            json={"username": "newbie", "password": "passw0rd!x"},
        )

        assert response.status_code == 200
        assert response.json()["access_token"]

    def test_existing_login_still_works(self, client, db_session):
        create_user(db_session, "olduser", "olduser@example.com", password="secret123")

        response = client.post(
            "/api/auth/login",
            json={"username": "olduser", "password": "secret123"},
        )

        assert response.status_code == 200
        assert response.json()["access_token"]

    def test_registered_admin_can_access_own_tenant_admin_tooling(self, client, db_session):
        _register(client)

        headers = login_headers(client, "newbie", "passw0rd!x")
        response = client.get("/api/users", headers=headers)

        # The registrant is the admin of their freshly provisioned tenant, so
        # admin endpoints work for them — they just start with a team of one
        # (themselves) since registration no longer nests them under anyone.
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["username"] == "newbie"

    def test_admin_management_still_works_and_is_tenant_scoped(self, client, db_session):
        """Admin tooling keeps working, but is isolated per organization.

        A self-registered user provisions their *own* tenant, so an admin of
        another organization can neither see nor manage that account.
        """
        admin = create_user(db_session, "root", "root@example.com", password="secret123", role=Role.admin)
        admin_headers = login_headers(client, "root", "secret123")

        _register(client)

        response = client.get("/api/users", headers=admin_headers)
        assert response.status_code == 200
        usernames = [u["username"] for u in response.json()]
        assert "root" in usernames
        assert "newbie" not in usernames

        registered = db_session.scalar(select(User).where(User.username == "newbie"))
        assert registered is not None
        assert registered.role is Role.admin
        patch = client.patch(
            f"/api/users/{registered.id}",
            headers=admin_headers,
            json={"role": "operator"},
        )
        assert patch.status_code == 404
        _ = admin