"""Generic submission endpoint tests.

Covers authentication (any active role may submit), form lifecycle gating,
dynamic field-type/settings validation, required fields, unknown-key
rejection, persistence, and cross-form isolation. Everything is driven by
database FormField definitions — no form-specific code.
"""

from sqlalchemy import select

from app.models import Role, Submission

from .conftest import create_user, login_headers

ADMIN_PASSWORD = "secret123"

SELECT_OPTIONS = [
    {"label": "Computer Science", "value": "cs"},
    {"label": "Mathematics", "value": "math"},
    {"label": "Physics", "value": "phys"},
]

RADIO_OPTIONS = [
    {"label": "Day", "value": "day"},
    {"label": "Night", "value": "night"},
]

EMPLOYEE_FIELDS = [
    {
        "field_key": "full_name",
        "label": "Full Name",
        "field_type": "text",
        "required": True,
    },
    {
        "field_key": "department",
        "label": "Department",
        "field_type": "select",
        "required": True,
        "settings": {"options": SELECT_OPTIONS},
    },
    {
        "field_key": "joining_date",
        "label": "Joining Date",
        "field_type": "date",
    },
    {
        "field_key": "email",
        "label": "Email",
        "field_type": "email",
    },
    {
        "field_key": "agree",
        "label": "Agree",
        "field_type": "checkbox",
        "required": True,
    },
]

VALID_EMPLOYEE_DATA = {
    "full_name": "Rahul",
    "department": "cs",
    "joining_date": "2026-09-19",
    "email": "rahul@example.com",
    "agree": True,
}


def _admin(client, db_session):
    create_user(db_session, "root", "root@example.com", password=ADMIN_PASSWORD, role=Role.admin)
    return login_headers(client, "root", ADMIN_PASSWORD)


def _headers(client, db_session, username, role):
    create_user(db_session, username, f"{username}@example.com", role=role)
    return login_headers(client, username)


def _create_form(client, headers, name="Employee Onboarding", fields=None, status="published"):
    response = client.post("/api/forms", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    form_id = response.json()["id"]
    for field in fields or []:
        result = client.post(f"/api/forms/{form_id}/fields", headers=headers, json=field)
        assert result.status_code == 201, result.text
    if status == "published":
        result = client.post(f"/api/forms/{form_id}/publish", headers=headers)
        assert result.status_code == 200, result.text
    elif status == "archived":
        result = client.post(f"/api/forms/{form_id}/publish", headers=headers)
        assert result.status_code == 200, result.text
        result = client.post(f"/api/forms/{form_id}/archive", headers=headers)
        assert result.status_code == 200, result.text
    return form_id


def _submit(client, headers, form_id, data):
    return client.post(f"/api/forms/{form_id}/submissions", headers=headers, json={"data": data})


class TestSubmissionAuthentication:
    def test_anonymous_submission_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        response = _submit(client, {}, form_id, VALID_EMPLOYEE_DATA)

        assert response.status_code == 401

    def test_admin_can_submit(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        response = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        assert response.status_code == 201

    def test_operator_can_submit(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        operator = _headers(client, db_session, "operator", Role.operator)

        response = _submit(client, operator, form_id, VALID_EMPLOYEE_DATA)

        assert response.status_code == 201

    def test_viewer_can_submit(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        viewer = _headers(client, db_session, "viewer", Role.viewer)

        response = _submit(client, viewer, form_id, VALID_EMPLOYEE_DATA)

        assert response.status_code == 201

    def test_viewer_can_fetch_published_definition(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        viewer = _headers(client, db_session, "viewer", Role.viewer)

        response = client.get(f"/api/forms/{form_id}/definition", headers=viewer)

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "published"
        assert [f["field_key"] for f in body["fields"]] == [
            f["field_key"] for f in EMPLOYEE_FIELDS
        ]

    def test_anonymous_definition_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        response = client.get(f"/api/forms/{form_id}/definition")

        assert response.status_code == 401


class TestFormLifecycle:
    def test_published_form_accepts_submission(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        response = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        assert response.status_code == 201

    def test_draft_form_rejects_submission(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS, status="draft")

        response = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        assert response.status_code == 400

    def test_archived_form_rejects_submission(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS, status="archived")

        response = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        assert response.status_code == 400

    def test_unknown_form_returns_404(self, client, db_session):
        admin = _admin(client, db_session)

        response = _submit(client, admin, 999999, {"full_name": "X"})

        assert response.status_code == 404

    def test_draft_definition_not_exposed(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS, status="draft")
        viewer = _headers(client, db_session, "viewer2", Role.viewer)

        response = client.get(f"/api/forms/{form_id}/definition", headers=viewer)

        assert response.status_code == 400


class TestRequiredFields:
    def test_missing_required_field_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        data = {**VALID_EMPLOYEE_DATA}
        del data["full_name"]
        response = _submit(client, admin, form_id, data)

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any(e["loc"][2] == "full_name" for e in detail)
        assert "required" in next(
            e["msg"] for e in detail if e["loc"][2] == "full_name"
        )

    def test_empty_required_field_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        response = _submit(
            client, admin, form_id, {**VALID_EMPLOYEE_DATA, "full_name": ""}
        )

        assert response.status_code == 422

    def test_required_select_without_value_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        data = {**VALID_EMPLOYEE_DATA}
        del data["department"]
        response = _submit(client, admin, form_id, data)

        assert response.status_code == 422
        assert any(e["loc"][2] == "department" for e in response.json()["detail"])

    def test_required_number_missing_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        fields = [{"field_key": "age", "label": "Age", "field_type": "number", "required": True}]
        form_id = _create_form(client, admin, name="Age form", fields=fields)

        response = _submit(client, admin, form_id, {})

        assert response.status_code == 422

    def test_required_checkbox_must_be_checked(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        unchecked = {**VALID_EMPLOYEE_DATA, "agree": False}
        response = _submit(client, admin, form_id, unchecked)

        assert response.status_code == 422
        assert any(e["loc"][2] == "agree" for e in response.json()["detail"])

        checked = _submit(
            client, admin, form_id, {**VALID_EMPLOYEE_DATA, "agree": True}
        )
        assert checked.status_code == 201

    def test_optional_fields_may_be_omitted(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        minimal = {"full_name": "Rahul", "department": "cs", "agree": True}
        response = _submit(client, admin, form_id, minimal)

        assert response.status_code == 201


class TestUnknownFields:
    def test_unknown_field_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        response = _submit(
            client, admin, form_id, {**VALID_EMPLOYEE_DATA, "random_field": "unexpected"}
        )

        assert response.status_code == 422
        assert any(
            e["loc"][2] == "random_field" and "Unknown" in e["msg"]
            for e in response.json()["detail"]
        )

    def test_unknown_field_fails_even_when_required_present(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        response = _submit(client, admin, form_id, {"full_name": "X", "hacker": "yes"})

        assert response.status_code == 422


class TestFieldTypeValidation:
    def test_text_min_length(self, client, db_session):
        admin = _admin(client, db_session)
        fields = [
            {
                "field_key": "code",
                "label": "Code",
                "field_type": "text",
                "settings": {"min_length": 2, "max_length": 5},
            }
        ]
        form_id = _create_form(client, admin, name="Codes", fields=fields)

        assert _submit(client, admin, form_id, {"code": "a"}).status_code == 422
        assert _submit(client, admin, form_id, {"code": "longer"}).status_code == 422
        assert _submit(client, admin, form_id, {"code": "ab12"}).status_code == 201

    def test_number_valid_forms(self, client, db_session):
        admin = _admin(client, db_session)
        fields = [
            {
                "field_key": "age",
                "label": "Age",
                "field_type": "number",
                "settings": {"min": 0, "max": 120},
            }
        ]
        form_id = _create_form(client, admin, name="Ages", fields=fields)

        assert _submit(client, admin, form_id, {"age": 30}).status_code == 201
        assert _submit(client, admin, form_id, {"age": 30.5}).status_code == 201
        assert _submit(client, admin, form_id, {"age": "42"}).status_code == 201

    def test_number_invalid_values(self, client, db_session):
        admin = _admin(client, db_session)
        fields = [
            {
                "field_key": "age",
                "label": "Age",
                "field_type": "number",
                "settings": {"min": 0, "max": 120},
            }
        ]
        form_id = _create_form(client, admin, name="Ages", fields=fields)

        assert _submit(client, admin, form_id, {"age": "abc"}).status_code == 422
        assert _submit(client, admin, form_id, {"age": -1}).status_code == 422
        assert _submit(client, admin, form_id, {"age": 150}).status_code == 422

    def test_number_step_enforced(self, client, db_session):
        admin = _admin(client, db_session)
        fields = [
            {
                "field_key": "rating",
                "label": "Rating",
                "field_type": "number",
                "settings": {"min": 0, "step": 5},
            }
        ]
        form_id = _create_form(client, admin, name="Ratings", fields=fields)

        assert _submit(client, admin, form_id, {"rating": 0}).status_code == 201
        assert _submit(client, admin, form_id, {"rating": 10}).status_code == 201
        assert _submit(client, admin, form_id, {"rating": 7}).status_code == 422

    def test_email_validation(self, client, db_session):
        admin = _admin(client, db_session)
        fields = [{"field_key": "email", "label": "Email", "field_type": "email"}]
        form_id = _create_form(client, admin, name="Emails", fields=fields)

        assert _submit(client, admin, form_id, {"email": "user@example.com"}).status_code == 201
        assert _submit(client, admin, form_id, {"email": "not-an-email"}).status_code == 422
        assert _submit(client, admin, form_id, {"email": 123}).status_code == 422

    def test_phone_validation(self, client, db_session):
        admin = _admin(client, db_session)
        fields = [{"field_key": "phone", "label": "Phone", "field_type": "phone"}]
        form_id = _create_form(client, admin, name="Phones", fields=fields)

        assert _submit(client, admin, form_id, {"phone": "+1 (555) 123-4567"}).status_code == 201
        assert _submit(client, admin, form_id, {"phone": "9876543210"}).status_code == 201
        assert _submit(client, admin, form_id, {"phone": "abc"}).status_code == 422

    def test_date_validation(self, client, db_session):
        admin = _admin(client, db_session)
        fields = [{"field_key": "joining_date", "label": "Date", "field_type": "date"}]
        form_id = _create_form(client, admin, name="Dates", fields=fields)

        assert _submit(client, admin, form_id, {"joining_date": "2026-09-19"}).status_code == 201
        assert _submit(client, admin, form_id, {"joining_date": "2026-13-45"}).status_code == 422
        assert _submit(client, admin, form_id, {"joining_date": "yesterday"}).status_code == 422

    def test_time_validation(self, client, db_session):
        admin = _admin(client, db_session)
        fields = [{"field_key": "start", "label": "Start", "field_type": "time"}]
        form_id = _create_form(client, admin, name="Times", fields=fields)

        assert _submit(client, admin, form_id, {"start": "14:30"}).status_code == 201
        assert _submit(client, admin, form_id, {"start": "14:30:45"}).status_code == 201
        assert _submit(client, admin, form_id, {"start": "25:99"}).status_code == 422

    def test_datetime_validation(self, client, db_session):
        admin = _admin(client, db_session)
        fields = [{"field_key": "meeting", "label": "Meeting", "field_type": "datetime"}]
        form_id = _create_form(client, admin, name="Meetings", fields=fields)

        assert _submit(client, admin, form_id, {"meeting": "2026-09-19T10:30:00"}).status_code == 201
        assert _submit(client, admin, form_id, {"meeting": "2026-09-19T10:30"}).status_code == 201
        assert _submit(client, admin, form_id, {"meeting": "not-a-date"}).status_code == 422

    def test_select_option_value(self, client, db_session):
        admin = _admin(client, db_session)
        fields = [{"field_key": "department", "label": "Dept", "field_type": "select", "settings": {"options": SELECT_OPTIONS}}]
        form_id = _create_form(client, admin, name="Depts", fields=fields)

        assert _submit(client, admin, form_id, {"department": "cs"}).status_code == 201
        assert _submit(client, admin, form_id, {"department": "Unknown Department"}).status_code == 422

    def test_select_option_label_accepted(self, client, db_session):
        admin = _admin(client, db_session)
        fields = [{"field_key": "department", "label": "Dept", "field_type": "select", "settings": {"options": SELECT_OPTIONS}}]
        form_id = _create_form(client, admin, name="Depts", fields=fields)

        response = _submit(client, admin, form_id, {"department": "Computer Science"})
        assert response.status_code == 201

    def test_radio_option_validation(self, client, db_session):
        admin = _admin(client, db_session)
        fields = [{"field_key": "shift", "label": "Shift", "field_type": "radio", "settings": {"options": RADIO_OPTIONS}}]
        form_id = _create_form(client, admin, name="Shifts", fields=fields)

        assert _submit(client, admin, form_id, {"shift": "day"}).status_code == 201
        assert _submit(client, admin, form_id, {"shift": "graveyard"}).status_code == 422

    def test_checkbox_representation(self, client, db_session):
        admin = _admin(client, db_session)
        fields = [{"field_key": "notify", "label": "Notify", "field_type": "checkbox"}]
        form_id = _create_form(client, admin, name="Opt-ins", fields=fields)

        assert _submit(client, admin, form_id, {"notify": True}).status_code == 201
        assert _submit(client, admin, form_id, {"notify": False}).status_code == 201
        assert _submit(client, admin, form_id, {"notify": "yes"}).status_code == 422

    def test_checkbox_value_required_when_no_fields_omit_data(self, client, db_session):
        admin = _admin(client, db_session)
        fields = [
            {"field_key": "note", "label": "Note", "field_type": "text"},
            {"field_key": "opt", "label": "Opt", "field_type": "checkbox"},
        ]
        form_id = _create_form(client, admin, name="Optional", fields=fields)

        assert _submit(client, admin, form_id, {"note": "hello"}).status_code == 201


class TestPersistence:
    def test_valid_submission_persisted(self, client, db_session):
        admin_user = create_user(
            db_session, "root", "root@example.com", password=ADMIN_PASSWORD, role=Role.admin
        )
        admin = login_headers(client, "root", ADMIN_PASSWORD)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        response = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        assert response.status_code == 201
        body = response.json()

        submission = db_session.scalar(select(Submission).where(Submission.id == body["id"]))
        assert submission is not None
        assert submission.form_id == form_id
        assert submission.submitted_by == admin_user.id
        assert submission.data == VALID_EMPLOYEE_DATA
        assert submission.submitted_at is not None

    def test_response_shape(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        response = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        body = response.json()
        assert set(body.keys()) == {
            "id",
            "form_id",
            "submitted_by",
            "data",
            "submitted_at",
            "updated_at",
        }
        assert "password_hash" not in response.text

    def test_stored_data_matches_submitted_data(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        response = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        stored = db_session.scalar(
            select(Submission).where(Submission.id == response.json()["id"])
        )
        assert stored.data == VALID_EMPLOYEE_DATA


class TestIsolation:
    def test_submission_cannot_use_another_forms_keys(self, client, db_session):
        admin = _admin(client, db_session)
        form_a = _create_form(client, admin, name="Form A", fields=EMPLOYEE_FIELDS)
        other_fields = [
            {"field_key": "student_name", "label": "Name", "field_type": "text", "required": True}
        ]
        form_b = _create_form(client, admin, name="Form B", fields=other_fields)

        response = _submit(
            client,
            admin,
            form_a,
            {
                "full_name": "Rahul",
                "department": "cs",
                "agree": True,
                "student_name": "Rahul",
            },
        )

        assert response.status_code == 422
        assert any(e["loc"][2] == "student_name" for e in response.json()["detail"])

        # The foreign keys were never accepted for form A, and form B's own
        # submission still works with its own definition.
        assert _submit(client, admin, form_b, {"student_name": "Rahul"}).status_code == 201

    def test_draft_fields_cannot_leak_into_published_submissions(self, client, db_session):
        admin = _admin(client, db_session)
        form_a = _create_form(client, admin, name="A", fields=EMPLOYEE_FIELDS)

        response = _submit(client, admin, form_a, {
            **VALID_EMPLOYEE_DATA,
            "not_a_field": 1,
        })
        assert response.status_code == 422