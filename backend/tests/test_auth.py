"""Authentication endpoint tests."""

from datetime import timedelta

from sqlalchemy import select

from app.core.security import create_access_token
from app.models import User

from .conftest import create_user, login_headers


class TestLogin:
    def test_login_with_valid_credentials(self, client, db_session):
        create_user(db_session, "alice", "alice@example.com", password="secret123")

        response = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "secret123"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]

    def test_login_with_email(self, client, db_session):
        create_user(db_session, "bob", "bob@example.com", password="secret123")

        response = client.post(
            "/api/auth/login",
            json={"username": "bob@example.com", "password": "secret123"},
        )

        assert response.status_code == 200
        assert response.json()["access_token"]

    def test_login_invalid_password(self, client, db_session):
        create_user(db_session, "alice", "alice@example.com", password="secret123")

        response = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "wrong-password"},
        )

        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        response = client.post(
            "/api/auth/login",
            json={"username": "ghost", "password": "whatever"},
        )

        assert response.status_code == 401

    def test_inactive_user_cannot_login(self, client, db_session):
        create_user(
            db_session,
            "disabled",
            "disabled@example.com",
            password="secret123",
            is_active=False,
        )

        response = client.post(
            "/api/auth/login",
            json={"username": "disabled", "password": "secret123"},
        )

        assert response.status_code == 401

    def test_login_updates_last_login_at(self, client, db_session):
        struct = create_user(db_session, "recent", "recent@example.com", password="secret123")
        assert struct.last_login_at is None

        login_headers(client, "recent", "secret123")

        db_session.expire_all()
        user = db_session.scalar(select(User).where(User.username == "recent"))
        assert user.last_login_at is not None


class TestMe:
    def test_me_without_token(self, client):
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_me_with_invalid_token(self, client):
        response = client.get(
            "/api/auth/me", headers={"Authorization": "Bearer not.a.valid.token"}
        )
        assert response.status_code == 401

    def test_me_with_expired_token(self, client, db_session):
        user = create_user(db_session, "expiry", "expiry@example.com")
        token = create_access_token(str(user.id), expires_delta=timedelta(minutes=-1))

        response = client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401

    def test_me_with_valid_token(self, client, db_session):
        create_user(db_session, "carol", "carol@example.com")

        headers = login_headers(client, "carol")
        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == 200
        body = response.json()
        assert body["username"] == "carol"
        assert body["email"] == "carol@example.com"
        assert body["role"] == "viewer"
        assert body["is_active"] is True
        assert "password_hash" not in body
        assert "password" not in body