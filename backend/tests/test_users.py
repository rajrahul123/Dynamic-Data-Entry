"""Admin user-management endpoint tests."""

from sqlalchemy import select

from app.models import Role, User

from .conftest import create_user, login_headers

ADMIN_PASSWORD = "secret123"


def _admin(client, db_session):
    create_user(db_session, "root", "root@example.com", password=ADMIN_PASSWORD, role=Role.admin)
    return login_headers(client, "root", ADMIN_PASSWORD)


class TestCreateUser:
    def test_admin_can_create_user(self, client, db_session):
        headers = _admin(client, db_session)

        response = client.post(
            "/api/users",
            headers=headers,
            json={
                "username": "new.user",
                "email": "new.user@example.com",
                "password": "passw0rd!x",
                "full_name": "New User",
                "role": "operator",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["username"] == "new.user"
        assert body["email"] == "new.user@example.com"
        assert body["role"] == "operator"
        assert body["is_active"] is True
        assert "password_hash" not in body

    def test_created_user_has_default_role_viewer(self, client, db_session):
        headers = _admin(client, db_session)

        response = client.post(
            "/api/users",
            headers=headers,
            json={
                "username": "plain",
                "email": "plain@example.com",
                "password": "passw0rd!x",
            },
        )

        assert response.status_code == 201
        assert response.json()["role"] == "viewer"

    def test_duplicate_username_rejected(self, client, db_session):
        create_user(db_session, "taken", "taken@example.com")
        headers = _admin(client, db_session)

        response = client.post(
            "/api/users",
            headers=headers,
            json={
                "username": "taken",
                "email": "other@example.com",
                "password": "passw0rd!x",
            },
        )

        assert response.status_code == 409

    def test_duplicate_email_rejected(self, client, db_session):
        create_user(db_session, "owner", "shared@example.com")
        headers = _admin(client, db_session)

        response = client.post(
            "/api/users",
            headers=headers,
            json={
                "username": "newbie",
                "email": "shared@example.com",
                "password": "passw0rd!x",
            },
        )

        assert response.status_code == 409

    def test_password_stored_hashed(self, client, db_session):
        headers = _admin(client, db_session)

        client.post(
            "/api/users",
            headers=headers,
            json={
                "username": "hashi",
                "email": "hashi@example.com",
                "password": "passw0rd!x",
            },
        )

        user = db_session.scalar(select(User).where(User.username == "hashi"))
        assert user is not None
        assert user.password_hash != "passw0rd!x"
        assert user.password_hash.startswith("$argon2")

    def test_password_hash_never_returned_by_api(self, client, db_session):
        headers = _admin(client, db_session)

        response = client.post(
            "/api/users",
            headers=headers,
            json={
                "username": "stealth",
                "email": "stealth@example.com",
                "password": "passw0rd!x",
            },
        )

        raw = response.text
        assert "password_hash" not in raw
        assert "passw0rd!x" not in raw


class TestListUsers:
    def test_list_users(self, client, db_session):
        create_user(db_session, "first", "first@example.com")
        create_user(db_session, "second", "second@example.com")
        headers = _admin(client, db_session)

        response = client.get("/api/users", headers=headers)

        assert response.status_code == 200
        usernames = [u["username"] for u in response.json()]
        assert "first" in usernames
        assert "second" in usernames


class TestUpdateUser:
    def test_admin_can_change_role(self, client, db_session):
        target = create_user(db_session, "switch", "switch@example.com")
        headers = _admin(client, db_session)

        response = client.patch(
            f"/api/users/{target.id}",
            headers=headers,
            json={"role": "admin"},
        )

        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    def test_admin_can_deactivate_user(self, client, db_session):
        target = create_user(db_session, "disableme", "disableme@example.com")
        headers = _admin(client, db_session)

        response = client.patch(
            f"/api/users/{target.id}",
            headers=headers,
            json={"is_active": False},
        )

        assert response.status_code == 200
        assert response.json()["is_active"] is False

        # Deactivated user can no longer log in.
        login = client.post(
            "/api/auth/login",
            json={"username": "disableme", "password": "password123"},
        )
        assert login.status_code == 401

    def test_admin_cannot_deactivate_self(self, client, db_session):
        admin_user = create_user(db_session, "root2", "root2@example.com", password=ADMIN_PASSWORD, role=Role.admin)
        headers = login_headers(client, "root2", ADMIN_PASSWORD)

        response = client.patch(
            f"/api/users/{admin_user.id}",
            headers=headers,
            json={"is_active": False},
        )

        assert response.status_code == 400

    def test_admin_cannot_demote_self(self, client, db_session):
        admin_user = create_user(db_session, "root2", "root2@example.com", password=ADMIN_PASSWORD, role=Role.admin)
        headers = login_headers(client, "root2", ADMIN_PASSWORD)

        response = client.patch(
            f"/api/users/{admin_user.id}",
            headers=headers,
            json={"role": "operator"},
        )

        assert response.status_code == 400

    def test_admin_can_reset_password(self, client, db_session):
        target = create_user(db_session, "reset", "reset@example.com", password="oldpassword")
        headers = _admin(client, db_session)

        response = client.patch(
            f"/api/users/{target.id}",
            headers=headers,
            json={"password": "brandnewpassword1"},
        )

        assert response.status_code == 200

        # Old password no longer works; new one does.
        assert client.post(
            "/api/auth/login", json={"username": "reset", "password": "oldpassword"}
        ).status_code == 401
        assert client.post(
            "/api/auth/login", json={"username": "reset", "password": "brandnewpassword1"}
        ).status_code == 200

    def test_update_unknown_user_returns_404(self, client, db_session):
        headers = _admin(client, db_session)
        response = client.patch("/api/users/999999", headers=headers, json={"role": "admin"})
        assert response.status_code == 404

    def test_update_duplicate_email_rejected(self, client, db_session):
        other = create_user(db_session, "holder", "holder@example.com")
        target = create_user(db_session, "changer", "changer@example.com")
        headers = _admin(client, db_session)

        response = client.patch(
            f"/api/users/{target.id}",
            headers=headers,
            json={"email": "holder@example.com"},
        )

        assert response.status_code == 409
        # Unrelated user should not be flagged as a conflict.
        _ = other