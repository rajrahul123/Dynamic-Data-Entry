"""Role-based authorization tests.

The admin-only user management router doubles as the protected endpoint used
to verify role enforcement on the backend.
"""

from app.models import Role

from .conftest import create_user, login_headers

PASSWORD = "secret123"


class TestRoleAuthorization:
    def test_admin_can_access_admin_endpoint(self, client, db_session):
        create_user(db_session, "admin1", "admin1@example.com", password=PASSWORD, role=Role.admin)

        headers = login_headers(client, "admin1", PASSWORD)
        response = client.get("/api/users", headers=headers)

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_operator_cannot_access_admin_endpoint(self, client, db_session):
        create_user(db_session, "op1", "op1@example.com", password=PASSWORD, role=Role.operator)

        headers = login_headers(client, "op1", PASSWORD)
        response = client.get("/api/users", headers=headers)

        assert response.status_code == 403

    def test_viewer_cannot_access_admin_endpoint(self, client, db_session):
        create_user(db_session, "view1", "view1@example.com", password=PASSWORD, role=Role.viewer)

        headers = login_headers(client, "view1", PASSWORD)
        response = client.get("/api/users", headers=headers)

        assert response.status_code == 403

    def test_unauthenticated_request_to_admin_endpoint(self, client):
        response = client.get("/api/users")
        assert response.status_code == 401

    def test_operator_accesses_authenticated_endpoint(self, client, db_session):
        create_user(db_session, "op2", "op2@example.com", password=PASSWORD, role=Role.operator)

        headers = login_headers(client, "op2", PASSWORD)
        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == 200
        assert response.json()["role"] == Role.operator.value