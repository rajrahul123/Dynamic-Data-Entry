"""Authentication endpoint tests."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import create_access_token, generate_reset_otp, hash_password
from app.models import User

from .conftest import create_user, login_headers

RESET_CODE_MESSAGE = (
    "If an account exists for that email, a password reset code has been sent."
)
INVALID_OTP_MESSAGE = "The reset code is invalid or has expired"


def _request_reset(client, monkeypatch, email: str) -> str:
    """POST forgot-password, capture the generated OTP, and return it.

    The real email sender is patched out so tests observe the OTP that a user
    would receive instead of relying on mail/log side effects.
    """
    captured: list[str] = []

    def fake_send(to_email: str, otp: str) -> None:
        captured.append(otp)

    monkeypatch.setattr(
        "app.api.routes.auth.send_password_reset_otp_email", fake_send
    )
    response = client.post("/api/auth/forgot-password", json={"email": email})
    assert response.status_code == 200, response.text
    assert len(captured) == 1, "expected exactly one OTP to be dispatched"
    otp = captured[0]
    assert len(otp) == 6 and otp.isdigit()
    return otp


class TestGenerateResetOtp:
    def test_returns_six_digits(self):
        otp = generate_reset_otp()
        assert len(otp) == 6

    def test_is_numeric_and_in_range(self):
        for _ in range(100):
            otp = generate_reset_otp()
            assert otp.isdigit()
            assert 100000 <= int(otp) <= 999999

    def test_fixed_width_even_for_small_values(self):
        for _ in range(50):
            otp = generate_reset_otp()
            assert len(otp) == 6, "codes must keep leading-significance width"

    def test_custom_digit_length(self):
        assert len(generate_reset_otp(8)) == 8

    def test_zero_digits_rejected(self):
        try:
            generate_reset_otp(0)
        except ValueError:
            return
        raise AssertionError("expected ValueError for zero-digit OTP")


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

    def test_login_with_email_case_insensitive(self, client, db_session):
        create_user(db_session, "caseuser", "caseuser@Example.COM", password="secret123")

        response = client.post(
            "/api/auth/login",
            json={"username": "caseuser@example.com", "password": "secret123"},
        )

        assert response.status_code == 200
        assert response.json()["access_token"]

    def test_login_with_email_wrong_password(self, client, db_session):
        create_user(db_session, "mailw", "mailw@example.com", password="secret123")

        response = client.post(
            "/api/auth/login",
            json={"username": "mailw@example.com", "password": "wrong-password"},
        )

        assert response.status_code == 401

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
        assert response.json()["detail"] == RESET_CODE_MESSAGE

    def test_valid_email_stores_otp_and_dispatches_code(self, client, db_session, monkeypatch):
        create_user(db_session, "otpuser", "otpuser@example.com", password="oldpass123")

        _request_reset(client, monkeypatch, "otpuser@example.com")

        db_session.expire_all()
        user = db_session.scalar(select(User).where(User.username == "otpuser"))
        assert user.reset_otp_hash is not None
        assert user.reset_otp_expires_at is not None

    def test_invalid_email_returns_same_generic_success(self, client, monkeypatch):
        captured: list[str] = []

        def fake_send(to_email: str, otp: str) -> None:
            captured.append(otp)

        monkeypatch.setattr(
            "app.api.routes.auth.send_password_reset_otp_email", fake_send
        )
        response = client.post(
            "/api/auth/forgot-password", json={"email": "ghost@example.com"}
        )

        assert response.status_code == 200
        # Identical body to the existing-email case: no account enumeration.
        assert response.json()["detail"] == RESET_CODE_MESSAGE
        # And no OTP was generated or "sent" for a nonexistent account.
        assert captured == []

    def test_malformed_email_rejected(self, client):
        response = client.post(
            "/api/auth/forgot-password", json={"email": "not-an-email"}
        )

        assert response.status_code == 422

    def test_rate_limited_after_third_request_per_minute(self, client, db_session, monkeypatch):
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
    def test_reset_with_valid_otp(self, client, db_session, monkeypatch):
        create_user(db_session, "resetme", "resetme@example.com", password="oldpass123")
        otp = _request_reset(client, monkeypatch, "resetme@example.com")

        response = client.post(
            "/api/auth/reset-password",
            json={"email": "resetme@example.com", "otp": otp, "new_password": "brandnew456"},
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

    def test_incorrect_otp_rejected(self, client, db_session, monkeypatch):
        create_user(db_session, "wrongotp", "wrongotp@example.com", password="oldpass123")
        otp = _request_reset(client, monkeypatch, "wrongotp@example.com")

        response = client.post(
            "/api/auth/reset-password",
            json={"email": "wrongotp@example.com", "otp": "000000", "new_password": "brandnew456"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == INVALID_OTP_MESSAGE

        # Password unchanged and a failed attempt does not consume the code.
        assert client.post(
            "/api/auth/login", json={"username": "wrongotp", "password": "oldpass123"}
        ).status_code == 200
        assert client.post(
            "/api/auth/reset-password",
            json={
                "email": "wrongotp@example.com",
                "otp": otp,
                "new_password": "brandnew456",
            },
        ).status_code == 200

    def test_expired_otp_rejected(self, client, db_session):
        user = create_user(db_session, "expired", "expired@example.com", password="oldpass123")
        user.reset_otp_hash = hash_password("123456")
        user.reset_otp_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/auth/reset-password",
            json={"email": "expired@example.com", "otp": "123456", "new_password": "brandnew456"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == INVALID_OTP_MESSAGE

        # Password unchanged.
        assert client.post(
            "/api/auth/login", json={"username": "expired", "password": "oldpass123"}
        ).status_code == 200

    def test_unknown_email_rejected(self, client, db_session, monkeypatch):
        create_user(db_session, "real", "real@example.com", password="oldpass123")
        _request_reset(client, monkeypatch, "real@example.com")

        response = client.post(
            "/api/auth/reset-password",
            json={"email": "ghost@example.com", "otp": "123456", "new_password": "brandnew456"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == INVALID_OTP_MESSAGE

    def test_successful_reset_consumes_otp(self, client, db_session, monkeypatch):
        create_user(db_session, "once", "once@example.com", password="oldpass123")
        otp = _request_reset(client, monkeypatch, "once@example.com")

        payload = {"email": "once@example.com", "otp": otp, "new_password": "brandnew456"}
        assert client.post("/api/auth/reset-password", json=payload).status_code == 200

        # Single-use: replaying the same code must fail.
        response = client.post("/api/auth/reset-password", json=payload)
        assert response.status_code == 400
        assert response.json()["detail"] == INVALID_OTP_MESSAGE

    def test_missing_stored_otp_rejected(self, client, db_session):
        create_user(db_session, "nocode", "nocode@example.com", password="oldpass123")

        response = client.post(
            "/api/auth/reset-password",
            json={"email": "nocode@example.com", "otp": "123456", "new_password": "brandnew456"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == INVALID_OTP_MESSAGE

    def test_non_numeric_otp_rejected(self, client):
        response = client.post(
            "/api/auth/reset-password",
            json={"email": "x@example.com", "otp": "abcdef", "new_password": "brandnew456"},
        )

        assert response.status_code == 422

    def test_new_password_too_short_rejected(self, client, db_session, monkeypatch):
        create_user(db_session, "shortpw", "shortpw@example.com", password="oldpass123")
        otp = _request_reset(client, monkeypatch, "shortpw@example.com")

        response = client.post(
            "/api/auth/reset-password",
            json={"email": "shortpw@example.com", "otp": otp, "new_password": "short"},
        )

        assert response.status_code == 422

    def test_missing_fields_rejected(self, client):
        response = client.post(
            "/api/auth/reset-password", json={"new_password": "brandnew456"}
        )

        assert response.status_code == 422

    def test_rate_limited_after_fifth_request_per_minute(self, client, db_session):
        create_user(db_session, "otpflood", "otpflood@example.com", password="oldpass123")
        user = db_session.scalar(select(User).where(User.username == "otpflood"))
        user.reset_otp_hash = hash_password("483920")
        user.reset_otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=1)
        db_session.add(user)
        db_session.commit()

        payload = {
            "email": "otpflood@example.com",
            "otp": "000000",
            "new_password": "brandnew456",
        }
        for _ in range(5):
            response = client.post("/api/auth/reset-password", json=payload)
            assert response.status_code == 400

        response = client.post("/api/auth/reset-password", json=payload)
        assert response.status_code == 429