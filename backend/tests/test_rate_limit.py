"""Per-IP rate limiting tests for the public auth endpoints.

Asserts that brute-force / account-spam attempts are throttled with HTTP 429
and a clear message. The limiter storage is global to the test process, so
``conftest`` resets the window before every test; these tests then exhaust
the per-IP budget within a single test.
"""

REGISTER_VALID = {
    "username": "newbie",
    "email": "newbie@example.com",
    "password": "passw0rd!x",
    "full_name": "Newbie User",
}

LOGIN_BAD = {"username": "nobody", "password": "wrong-password"}

TOO_MANY_MARKER = "Too many requests"


class TestLoginRateLimit:
    def test_login_throttled_after_five_attempts(self, client):
        for _ in range(5):
            response = client.post("/api/auth/login", json=LOGIN_BAD)
            assert response.status_code == 401

        response = client.post("/api/auth/login", json=LOGIN_BAD)
        assert response.status_code == 429
        assert TOO_MANY_MARKER in response.json()["detail"]

    def test_login_successful_attempts_also_count(self, client, db_session):
        from .conftest import create_user, login_headers

        create_user(db_session, "u1", "u1@example.com")
        login_headers(client, "u1")
        login_headers(client, "u1")
        login_headers(client, "u1")
        login_headers(client, "u1")

        response = client.post("/api/auth/login", json={"username": "u1", "password": "password123"})
        assert response.status_code == 200

        response = client.post("/api/auth/login", json={"username": "u1", "password": "password123"})
        assert response.status_code == 429

    def test_login_429_includes_rate_limit_headers(self, client):
        for _ in range(5):
            client.post("/api/auth/login", json=LOGIN_BAD)

        response = client.post("/api/auth/login", json=LOGIN_BAD)
        assert response.status_code == 429
        assert response.headers.get("x-ratelimit-limit") == "5"
        assert response.headers.get("x-ratelimit-remaining") == "0"
        assert "retry-after" in response.headers


class TestRegisterRateLimit:
    def test_register_throttled_after_three_registrations(self, client):
        for index in range(3):
            payload = {
                **REGISTER_VALID,
                "username": f"newbie{index}",
                "email": f"newbie{index}@example.com",
            }
            response = client.post("/api/auth/register", json=payload)
            assert response.status_code == 201

        response = client.post(
            "/api/auth/register",
            json={**REGISTER_VALID, "username": "surplus", "email": "surplus@example.com"},
        )
        assert response.status_code == 429
        assert TOO_MANY_MARKER in response.json()["detail"]

    def test_conflicting_register_attempts_also_count(self, client):
        # First request succeeds, the next two are duplicate-username 409s, but
        # each attempt that reaches the endpoint consumes one budget slot.
        for index, expected in enumerate((201, 409, 409)):
            response = client.post("/api/auth/register", json=REGISTER_VALID)
            assert response.status_code == expected

        response = client.post("/api/auth/register", json=REGISTER_VALID)
        assert response.status_code == 429


class TestOtherEndpointsUnaffected:
    def test_health_and_login_share_no_budget(self, client):
        payload = {"username": "nobody", "password": "wrong-password"}
        for _ in range(5):
            client.post("/api/auth/login", json=payload)
            assert client.get("/api/health").status_code == 200

        response = client.post("/api/auth/login", json=payload)
        assert response.status_code == 429
        assert client.get("/api/health").status_code == 200