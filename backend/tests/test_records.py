"""Phase 4 record-management endpoint tests.

Covers the generic submission list / detail / update / delete endpoints plus
lifecycle semantics: pagination, role access (admin/operator/viewer/anonymous),
cross-form isolation, dynamic validation reuse on edits, archived-record
retention and the historical-record editing behavior of archived forms.
"""

from sqlalchemy import select

from app.models import Form, FormField, Role, Submission

from .conftest import create_user, login_headers

ADMIN_PASSWORD = "secret123"

SELECT_OPTIONS = [
    {"label": "Engineering", "value": "eng"},
    {"label": "Sales", "value": "sales"},
]

EMPLOYEE_FIELDS = [
    {"field_key": "full_name", "label": "Full Name", "field_type": "text", "required": True},
    {
        "field_key": "department",
        "label": "Department",
        "field_type": "select",
        "required": True,
        "settings": {"options": SELECT_OPTIONS},
    },
    {"field_key": "email", "label": "Email", "field_type": "email"},
    {"field_key": "agree", "label": "Agree", "field_type": "checkbox", "required": True},
]

VALID_EMPLOYEE_DATA = {
    "full_name": "Rahul Ahirwar",
    "department": "eng",
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
    response = client.post(f"/api/forms/{form_id}/submissions", headers=headers, json={"data": data})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _list(client, headers, form_id, **params):
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return client.get(f"/api/forms/{form_id}/submissions?{query}", headers=headers)


def _detail(client, headers, form_id, submission_id):
    return client.get(f"/api/forms/{form_id}/submissions/{submission_id}", headers=headers)


def _update(client, headers, form_id, submission_id, data):
    return client.patch(
        f"/api/forms/{form_id}/submissions/{submission_id}",
        headers=headers,
        json={"data": data},
    )


def _delete(client, headers, form_id, submission_id):
    return client.delete(f"/api/forms/{form_id}/submissions/{submission_id}", headers=headers)


class TestListRecords:
    def test_anonymous_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        response = _list(client, {}, form_id)

        assert response.status_code == 401

    def test_admin_allowed(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        response = _list(client, admin, form_id)

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1

    def test_operator_allowed(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)
        operator = _headers(client, db_session, "operator", Role.operator)

        response = _list(client, operator, form_id)

        assert response.status_code == 200

    def test_viewer_allowed(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)
        viewer = _headers(client, db_session, "viewer", Role.viewer)

        response = _list(client, viewer, form_id)

        assert response.status_code == 200

    def test_unknown_form_404(self, client, db_session):
        admin = _admin(client, db_session)

        response = _list(client, admin, 999999)

        assert response.status_code == 404

    def test_total_count(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        for _ in range(5):
            _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        body = _list(client, admin, form_id).json()

        assert body["total"] == 5
        assert len(body["items"]) == 5

    def test_limit_works(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        for _ in range(5):
            _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        body = _list(client, admin, form_id, limit=2).json()

        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["limit"] == 2
        assert body["offset"] == 0

    def test_offset_works(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        for _ in range(5):
            _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        page1 = _list(client, admin, form_id, limit=2, offset=0).json()
        page2 = _list(client, admin, form_id, limit=2, offset=2).json()
        page3 = _list(client, admin, form_id, limit=2, offset=4).json()

        ids1 = {item["id"] for item in page1["items"]}
        ids2 = {item["id"] for item in page2["items"]}
        ids3 = {item["id"] for item in page3["items"]}

        assert len(ids1) == 2 and len(ids2) == 2 and len(ids3) == 1
        assert ids1.isdisjoint(ids2) and ids2.isdisjoint(ids3) and ids1.isdisjoint(ids3)
        assert page3["total"] == 5

    def test_records_belong_to_requested_form(self, client, db_session):
        admin = _admin(client, db_session)
        form_a = _create_form(client, admin, name="Form A", fields=EMPLOYEE_FIELDS)
        form_b = _create_form(client, admin, name="Form B", fields=EMPLOYEE_FIELDS)
        for _ in range(3):
            _submit(client, admin, form_a, VALID_EMPLOYEE_DATA)
        for _ in range(2):
            _submit(client, admin, form_b, VALID_EMPLOYEE_DATA)

        body = _list(client, admin, form_a).json()

        assert body["total"] == 3
        assert all(item["form_id"] == form_a for item in body["items"])

    def test_item_shape_no_secrets(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        body = _list(client, admin, form_id).json()

        item = body["items"][0]
        assert {
            "id",
            "form_id",
            "submitted_by",
            "submitted_by_username",
            "submitted_by_full_name",
            "data",
            "submitted_at",
            "updated_at",
        } <= set(item.keys())
        assert "password_hash" not in _list(client, admin, form_id).text


class TestDetailRecord:
    def test_anonymous_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        response = _detail(client, {}, form_id, submission_id)

        assert response.status_code == 401

    def test_all_roles_allowed(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)
        operator = _headers(client, db_session, "operator", Role.operator)
        viewer = _headers(client, db_session, "viewer", Role.viewer)

        assert _detail(client, admin, form_id, submission_id).status_code == 200
        assert _detail(client, operator, form_id, submission_id).status_code == 200
        assert _detail(client, viewer, form_id, submission_id).status_code == 200

    def test_unknown_form_404(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        response = _detail(client, admin, 999999, submission_id)

        assert response.status_code == 404

    def test_unknown_submission_404(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        response = _detail(client, admin, form_id, 999999)

        assert response.status_code == 404

    def test_cross_form_submission_not_exposed(self, client, db_session):
        admin = _admin(client, db_session)
        form_a = _create_form(client, admin, name="Form A", fields=EMPLOYEE_FIELDS)
        form_b = _create_form(client, admin, name="Form B", fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_b, VALID_EMPLOYEE_DATA)

        response = _detail(client, admin, form_a, submission_id)

        assert response.status_code == 404
        assert _detail(client, admin, form_b, submission_id).status_code == 200

    def test_detail_shape(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        body = _detail(client, admin, form_id, submission_id).json()

        assert body["id"] == submission_id
        assert body["form_id"] == form_id
        assert body["data"] == VALID_EMPLOYEE_DATA
        assert "submitted_at" in body
        assert "updated_at" in body
        assert "password_hash" not in _detail(client, admin, form_id, submission_id).text


class TestUpdateRecord:
    def test_anonymous_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        response = _update(client, {}, form_id, submission_id, VALID_EMPLOYEE_DATA)

        assert response.status_code == 401

    def test_viewer_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)
        viewer = _headers(client, db_session, "viewer", Role.viewer)

        response = _update(client, viewer, form_id, submission_id, VALID_EMPLOYEE_DATA)

        assert response.status_code == 403

    def test_admin_success(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        updated = {**VALID_EMPLOYEE_DATA, "full_name": "Rahul Ahirwar Updated"}
        response = _update(client, admin, form_id, submission_id, updated)

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["full_name"] == "Rahul Ahirwar Updated"
        assert body["id"] == submission_id

        persisted = db_session.scalar(select(Submission).where(Submission.id == submission_id))
        assert persisted.data == updated

    def test_operator_success(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)
        operator = _headers(client, db_session, "operator", Role.operator)

        response = _update(client, operator, form_id, submission_id, VALID_EMPLOYEE_DATA)

        assert response.status_code == 200

    def test_unknown_form_404(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        response = _update(client, admin, 999999, submission_id, VALID_EMPLOYEE_DATA)

        assert response.status_code == 404

    def test_unknown_submission_404(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        response = _update(client, admin, form_id, 999999, VALID_EMPLOYEE_DATA)

        assert response.status_code == 404

    def test_cross_form_update_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_a = _create_form(client, admin, name="Form A", fields=EMPLOYEE_FIELDS)
        form_b = _create_form(client, admin, name="Form B", fields=EMPLOYEE_FIELDS)
        submission_b = _submit(client, admin, form_b, VALID_EMPLOYEE_DATA)

        response = _update(client, admin, form_a, submission_b, VALID_EMPLOYEE_DATA)

        assert response.status_code == 404
        persisted = db_session.scalar(select(Submission).where(Submission.id == submission_b))
        assert persisted.data == VALID_EMPLOYEE_DATA

    def test_missing_required_field_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        response = _update(client, admin, form_id, submission_id, {"department": "eng", "agree": True})

        assert response.status_code == 422
        assert any(e["loc"][2] == "full_name" for e in response.json()["detail"])

    def test_invalid_field_type_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        response = _update(
            client,
            admin,
            form_id,
            submission_id,
            {**VALID_EMPLOYEE_DATA, "email": "not-an-email"},
        )

        assert response.status_code == 422
        assert any(e["loc"][2] == "email" for e in response.json()["detail"])

    def test_invalid_checkbox_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        response = _update(
            client, admin, form_id, submission_id, {**VALID_EMPLOYEE_DATA, "agree": False}
        )

        assert response.status_code == 422

    def test_unknown_field_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        response = _update(
            client, admin, form_id, submission_id, {**VALID_EMPLOYEE_DATA, "hacker_key": "x"}
        )

        assert response.status_code == 422
        assert any(e["loc"][2] == "hacker_key" and "Unknown" in e["msg"] for e in response.json()["detail"])

    def test_invalid_select_option_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        response = _update(
            client, admin, form_id, submission_id, {**VALID_EMPLOYEE_DATA, "department": "bogus"}
        )

        assert response.status_code == 422
        assert any(e["loc"][2] == "department" for e in response.json()["detail"])

    def test_invalid_number_constraints_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        fields = [
            {"field_key": "full_name", "label": "Name", "field_type": "text", "required": True},
            {"field_key": "age", "label": "Age", "field_type": "number", "settings": {"min": 0, "max": 120}},
        ]
        form_id = _create_form(client, admin, name="Ages", fields=fields)
        submission_id = _submit(client, admin, form_id, {"full_name": "Rahul", "age": 30})

        response = _update(client, admin, form_id, submission_id, {"full_name": "Rahul", "age": 999})

        assert response.status_code == 422
        assert any(e["loc"][2] == "age" for e in response.json()["detail"])

    def test_archived_form_existing_record_editable(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS, status="published")
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)
        assert client.post(f"/api/forms/{form_id}/archive", headers=admin).status_code == 200

        response = _update(
            client, admin, form_id, submission_id, {**VALID_EMPLOYEE_DATA, "full_name": "Edited While Archived"}
        )

        assert response.status_code == 200
        assert response.json()["data"]["full_name"] == "Edited While Archived"


class TestDeleteRecord:
    def test_anonymous_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        response = _delete(client, {}, form_id, submission_id)

        assert response.status_code == 401

    def test_viewer_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)
        viewer = _headers(client, db_session, "viewer", Role.viewer)

        response = _delete(client, viewer, form_id, submission_id)

        assert response.status_code == 403

    def test_admin_204(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        response = _delete(client, admin, form_id, submission_id)

        assert response.status_code == 204

    def test_operator_204(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)
        operator = _headers(client, db_session, "operator", Role.operator)

        response = _delete(client, operator, form_id, submission_id)

        assert response.status_code == 204

    def test_unknown_form_404(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        response = _delete(client, admin, 999999, submission_id)

        assert response.status_code == 404

    def test_unknown_submission_404(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)

        response = _delete(client, admin, form_id, 999999)

        assert response.status_code == 404

    def test_cross_form_delete_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_a = _create_form(client, admin, name="Form A", fields=EMPLOYEE_FIELDS)
        form_b = _create_form(client, admin, name="Form B", fields=EMPLOYEE_FIELDS)
        submission_b = _submit(client, admin, form_b, VALID_EMPLOYEE_DATA)

        response = _delete(client, admin, form_a, submission_b)

        assert response.status_code == 404
        assert _detail(client, admin, form_b, submission_b).status_code == 200

    def test_record_removed_form_intact_others_intact(self, client, db_session):
        admin_user = create_user(
            db_session, "root", "root@example.com", password=ADMIN_PASSWORD, role=Role.admin
        )
        admin = login_headers(client, "root", ADMIN_PASSWORD)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS)
        target = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)
        survivor = _submit(client, admin, form_id, {**VALID_EMPLOYEE_DATA, "full_name": "Survivor"})

        assert _delete(client, admin, form_id, target).status_code == 204

        assert _detail(client, admin, form_id, target).status_code == 404
        stored_form = db_session.get(Form, form_id)
        assert stored_form is not None
        assert stored_form.name == "Employee Onboarding"
        assert stored_form.created_by == admin_user.id
        tracked = db_session.scalar(
            select(Submission).where(Submission.id == survivor)
        )
        assert tracked is not None
        assert tracked.data["full_name"] == "Survivor"
        fields = db_session.scalars(
            select(FormField).where(FormField.form_id == form_id)
        ).all()
        assert len(fields) == len(EMPLOYEE_FIELDS)


class TestLifecycle:
    def test_published_records_viewable(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS, status="published")
        _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        assert _list(client, admin, form_id).status_code == 200

    def test_archived_records_viewable(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS, status="published")
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)
        assert client.post(f"/api/forms/{form_id}/archive", headers=admin).status_code == 200

        assert _list(client, admin, form_id).status_code == 200
        assert _list(client, admin, form_id).json()["total"] == 1
        assert _detail(client, admin, form_id, submission_id).status_code == 200

    def test_archived_existing_records_editable_and_deletable(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS, status="published")
        submission_id = _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)
        assert client.post(f"/api/forms/{form_id}/archive", headers=admin).status_code == 200

        assert _update(client, admin, form_id, submission_id, VALID_EMPLOYEE_DATA).status_code == 200
        assert _delete(client, admin, form_id, submission_id).status_code == 204
        assert _list(client, admin, form_id).json()["total"] == 0

    def test_archived_form_rejects_new_submissions(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS, status="archived")

        response = client.post(
            f"/api/forms/{form_id}/submissions", headers=admin, json={"data": VALID_EMPLOYEE_DATA}
        )

        assert response.status_code == 400

    def test_draft_records_hidden(self, client, db_session):
        admin_user = create_user(
            db_session, "root", "root@example.com", password=ADMIN_PASSWORD, role=Role.admin
        )
        admin = login_headers(client, "root", ADMIN_PASSWORD)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS, status="draft")
        persisted = Submission(
            form_id=form_id, submitted_by=admin_user.id, tenant_id=admin_user.tenant_id,
            data=VALID_EMPLOYEE_DATA,
        )
        db_session.add(persisted)
        db_session.commit()
        db_session.refresh(persisted)

        assert _list(client, admin, form_id).status_code == 400
        assert _detail(client, admin, form_id, persisted.id).status_code == 400

    def test_draft_record_management_blocked(self, client, db_session):
        # Draft forms are invisible to record operations: even legacy records
        # inserted directly into the DB cannot be listed, edited, or deleted.
        admin_user = create_user(
            db_session, "root", "root@example.com", password=ADMIN_PASSWORD, role=Role.admin
        )
        admin = login_headers(client, "root", ADMIN_PASSWORD)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS, status="draft")
        persisted = Submission(
            form_id=form_id, submitted_by=admin_user.id, tenant_id=admin_user.tenant_id,
            data=VALID_EMPLOYEE_DATA,
        )
        db_session.add(persisted)
        db_session.commit()
        db_session.refresh(persisted)

        bad = _update(client, admin, form_id, persisted.id, {"hacker": True})
        assert bad.status_code == 400

        good = _update(client, admin, form_id, persisted.id, VALID_EMPLOYEE_DATA)
        assert good.status_code == 400

        deleted = _delete(client, admin, form_id, persisted.id)
        assert deleted.status_code == 400

    def test_archived_definition_exposed_for_records(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS, status="archived")
        viewer = _headers(client, db_session, "viewer", Role.viewer)

        response = client.get(f"/api/forms/{form_id}/definition", headers=viewer)

        assert response.status_code == 200
        assert [f["field_key"] for f in response.json()["fields"]] == [
            f["field_key"] for f in EMPLOYEE_FIELDS
        ]

    def test_draft_definition_still_hidden(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=EMPLOYEE_FIELDS, status="draft")
        viewer = _headers(client, db_session, "viewer", Role.viewer)

        response = client.get(f"/api/forms/{form_id}/definition", headers=viewer)

        assert response.status_code == 400


class TestAvailableForms:
    def test_anonymous_rejected(self, client, db_session):
        response = client.get("/api/records/forms")

        assert response.status_code == 401

    def test_non_admin_can_list_available_forms(self, client, db_session):
        admin = _admin(client, db_session)
        published = _create_form(client, admin, name="Active", fields=EMPLOYEE_FIELDS, status="published")
        archived = _create_form(client, admin, name="Old", fields=EMPLOYEE_FIELDS, status="archived")
        _create_form(client, admin, name="Drafty", fields=EMPLOYEE_FIELDS, status="draft")
        operator = _headers(client, db_session, "operator", Role.operator)

        response = client.get("/api/records/forms", headers=operator)

        assert response.status_code == 200
        ids = {form["id"] for form in response.json()}
        assert ids == {published, archived}
        assert all("fields" not in form for form in response.json())