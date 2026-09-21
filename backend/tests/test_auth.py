"""Authentication endpoint tests."""

from datetime import timedelta

from sqlalchemy import select

from app.core.security import create_access_token, create_password_reset_token
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


class TestChangePassword:
    def test_requires_authentication(self, client):
        response = client.post(
            "/api/auth/change-password",
            json={"current_password": "oldpass123", "new_password": "newpass456"},
        )

        assert response.status_code == 401

    def test_successful_password_change(self, client, db_session):
        create_user(db_session, "changer", "changer@example.com", password="oldpass123")
        headers = login_headers(client, "changer", "oldpass123")

        response = client.post(
            "/api/auth/change-password",
            headers=headers,
            json={"current_password": "oldpass123", "new_password": "newpass456"},
        )

        assert response.status_code == 200
        assert response.json()["detail"] == "Password updated successfully"

        # The old password no longer works; the new one does.
        assert client.post(
            "/api/auth/login", json={"username": "changer", "password": "oldpass123"}
        ).status_code == 401
        assert client.post(
            "/api/auth/login", json={"username": "changer", "password": "newpass456"}
        ).status_code == 200

    def test_incorrect_current_password_rejected(self, client, db_session):
        create_user(db_session, "changer2", "changer2@example.com", password="oldpass123")
        headers = login_headers(client, "changer2", "oldpass123")

        response = client.post(
            "/api/auth/change-password",
            headers=headers,
            json={"current_password": "wrong-password", "new_password": "newpass456"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Incorrect current password"

        # Nothing changed: the existing password still authenticates.
        assert client.post(
            "/api/auth/login", json={"username": "changer2", "password": "oldpass123"}
        ).status_code == 200

    def test_new_password_too_short_rejected(self, client, db_session):
        create_user(db_session, "changer3", "changer3@example.com", password="oldpass123")
        headers = login_headers(client, "changer3", "oldpass123")

        response = client.post(
            "/api/auth/change-password",
            headers=headers,
            json={"current_password": "oldpass123", "new_password": "short"},
        )

        assert response.status_code == 422

    def test_missing_fields_rejected(self, client, db_session):
        create_user(db_session, "changer4", "changer4@example.com", password="oldpass123")
        headers = login_headers(client, "changer4", "oldpass123")

        response = client.post(
            "/api/auth/change-password", headers=headers, json={"new_password": "newpass456"}
        )

        assert response.status_code == 422

    def test_extra_fields_rejected(self, client, db_session):
        create_user(db_session, "changer5", "changer5@example.com", password="oldpass123")
        headers = login_headers(client, "changer5", "oldpass123")

        response = client.post(
            "/api/auth/change-password",
            headers=headers,
            json={
                "current_password": "oldpass123",
                "new_password": "newpass456",
                "role": "admin",
            },
        )

        assert response.status_code == 422


class TestForgotPassword:
    def test_valid_email_returns_generic_success(self, client, db_session):
        create_user(db_session, "forgot", "forgot@example.com", password="oldpass123")

        response = client.post(
            "/api/auth/forgot-password", json={"email": "forgot@example.com"}
        )

        assert response.status_code == 200
        assert response.json()["detail"] == (
            "If an account exists for that email, a password reset link has been sent."
        )

    def test_invalid_email_returns_same_generic_success(self, client):
        response = client.post(
            "/api/auth/forgot-password", json={"email": "ghost@example.com"}
        )

        assert response.status_code == 200
        # Identical body to the existing-email case: no account enumeration.
        assert response.json()["detail"] == (
            "If an account exists for that email, a password reset link has been sent."
        )

    def test_malformed_email_rejected(self, client):
        response = client.post(
            "/api/auth/forgot-password", json={"email": "not-an-email"}
        )

        assert response.status_code == 422

    def test_rate_limited_after_third_request_per_minute(self, client, db_session):
        create_user(db_session, "flooded", "flooded@example.com", password="oldpass123")

        for _ in range(3):
            response = client.post(
                "/api/auth/forgot-password", json={"email": "flooded@example.com"}
            )
            assert response.status_code == 200

        response = client.post(
            "/api/auth/forgot-password", json={"email": "flooded@example.com"}
        )

        assert response.status_code == 429


class TestResetPassword:
    def test_reset_with_valid_token(self, client, db_session):
        user = create_user(db_session, "resetme", "resetme@example.com", password="oldpass123")
        token = create_password_reset_token(str(user.id))

        response = client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "brandnew456"},
        )

        assert response.status_code == 200
        assert response.json()["detail"] == "Your password has been reset successfully"

        # Old password no longer works; new one does.
        assert client.post(
            "/api/auth/login", json={"username": "resetme", "password": "oldpass123"}
        ).status_code == 401
        assert client.post(
            "/api/auth/login", json={"username": "resetme", "password": "brandnew456"}
        ).status_code == 200

    def test_expired_token_rejected(self, client, db_session):
        user = create_user(db_session, "expired", "expired@example.com", password="oldpass123")
        token = create_password_reset_token(str(user.id), expires_delta=timedelta(minutes=-1))

        response = client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "brandnew456"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "The reset token is invalid or has expired"

        # Password unchanged.
        assert client.post(
            "/api/auth/login", json={"username": "expired", "password": "oldpass123"}
        ).status_code == 200

    def test_garbage_token_rejected(self, client):
        response = client.post(
            "/api/auth/reset-password",
            json={"token": "not.a.real.token", "new_password": "brandnew456"},
        )

        assert response.status_code == 400

    def test_access_token_cannot_be_used_as_reset_token(self, client, db_session):
        user = create_user(db_session, "confused", "confused@example.com", password="oldpass123")
        access_token = create_access_token(str(user.id))

        response = client.post(
            "/api/auth/reset-password",
            json={"token": access_token, "new_password": "brandnew456"},
        )

        assert response.status_code == 400

    def test_new_password_too_short_rejected(self, client, db_session):
        user = create_user(db_session, "shortpw", "shortpw@example.com", password="oldpass123")
        token = create_password_reset_token(str(user.id))

        response = client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "short"},
        )

        assert response.status_code == 422

    def test_missing_fields_rejected(self, client):
        response = client.post(
            "/api/auth/reset-password", json={"new_password": "brandnew456"}
        )

        assert response.status_code == 422