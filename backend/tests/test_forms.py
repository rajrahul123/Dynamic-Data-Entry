"""Dynamic form and form-field API tests.

Covers form CRUD and lifecycle (draft -> published -> archived), field CRUD,
reordering, per-type settings validation, and role-based access control.
"""

from sqlalchemy import select

from app.models import Form, FormField, Role, User

from .conftest import create_user, login_headers

ADMIN_PASSWORD = "secret123"

SELECT_SETTINGS = {
    "options": [
        {"label": "Option A", "value": "a"},
        {"label": "Option B", "value": "b"},
    ]
}


def _admin(client, db_session):
    create_user(db_session, "root", "root@example.com", password=ADMIN_PASSWORD, role=Role.admin)
    return login_headers(client, "root", ADMIN_PASSWORD)


def _create_form(client, headers, name="Test Form"):
    response = client.post("/api/forms", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def _add_field(client, headers, form_id, payload):
    response = client.post(f"/api/forms/{form_id}/fields", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


class TestCreateForm:
    def test_admin_can_create_form(self, client, db_session):
        headers = _admin(client, db_session)

        response = client.post(
            "/api/forms", headers=headers, json={"name": "Student Form", "description": "Admissions"}
        )

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Student Form"
        assert body["description"] == "Admissions"
        assert body["status"] == "draft"
        assert body["published_at"] is None
        assert body["fields"] == []
        assert "created_by" in body

    def test_created_by_is_admin(self, client, db_session):
        admin_user = create_user(
            db_session, "root", "root@example.com", password=ADMIN_PASSWORD, role=Role.admin
        )
        headers = login_headers(client, "root", ADMIN_PASSWORD)

        response = client.post("/api/forms", headers=headers, json={"name": "X"})

        assert response.status_code == 201
        assert response.json()["created_by"] == admin_user.id

    def test_empty_name_rejected(self, client, db_session):
        headers = _admin(client, db_session)
        response = client.post("/api/forms", headers=headers, json={"name": ""})
        assert response.status_code == 422


class TestListAndGetForm:
    def test_list_returns_forms_with_fields(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers, "Full Form")
        _add_field(client, headers, form["id"], {"field_key": "student_name", "label": "Name", "field_type": "text"})

        response = client.get("/api/forms", headers=headers)

        assert response.status_code == 200
        forms = response.json()
        matching = [f for f in forms if f["id"] == form["id"]]
        assert len(matching) == 1
        assert matching[0]["fields"][0]["field_key"] == "student_name"

    def test_list_filters_by_status(self, client, db_session):
        headers = _admin(client, db_session)
        draft = _create_form(client, headers, "Draft")
        published = _create_form(client, headers, "Published")
        client.post(f"/api/forms/{published['id']}/fields", headers=headers, json={
            "field_key": "x", "label": "X", "field_type": "text"
        })
        client.post(f"/api/forms/{published['id']}/publish", headers=headers)

        drafts = client.get("/api/forms?status=draft", headers=headers).json()
        published_list = client.get("/api/forms?status=published", headers=headers).json()

        assert [f["id"] for f in drafts] == [draft["id"]]
        assert [f["id"] for f in published_list] == [published["id"]]

    def test_get_form_by_id(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers, "Fetch me")
        _add_field(client, headers, form["id"], {"field_key": "a", "label": "A", "field_type": "text"})

        response = client.get(f"/api/forms/{form['id']}", headers=headers)

        assert response.status_code == 200
        assert response.json()["name"] == "Fetch me"
        assert len(response.json()["fields"]) == 1

    def test_get_unknown_form_returns_404(self, client, db_session):
        headers = _admin(client, db_session)
        response = client.get("/api/forms/999999", headers=headers)
        assert response.status_code == 404


class TestUpdateForm:
    def test_admin_can_rename_draft(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers, "Old name")

        response = client.patch(
            f"/api/forms/{form['id']}", headers=headers, json={"name": "New name", "description": None}
        )

        assert response.status_code == 200
        assert response.json()["name"] == "New name"
        assert response.json()["description"] is None

    def test_published_form_cannot_be_edited(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers, "Locked")
        _add_field(client, headers, form["id"], {"field_key": "x", "label": "X", "field_type": "text"})
        client.post(f"/api/forms/{form['id']}/publish", headers=headers)

        response = client.patch(f"/api/forms/{form['id']}", headers=headers, json={"name": "Hacked"})

        assert response.status_code == 409

    def test_update_unknown_form_returns_404(self, client, db_session):
        headers = _admin(client, db_session)
        response = client.patch("/api/forms/999999", headers=headers, json={"name": "X"})
        assert response.status_code == 404


class TestFormLifecycle:
    def test_publish_requires_at_least_one_field(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers, "Empty")

        response = client.post(f"/api/forms/{form['id']}/publish", headers=headers)

        assert response.status_code == 400

    def test_publish_sets_status_and_published_at(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers, "Ready")
        _add_field(client, headers, form["id"], {"field_key": "x", "label": "X", "field_type": "text"})

        response = client.post(f"/api/forms/{form['id']}/publish", headers=headers)

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "published"
        assert body["published_at"] is not None

    def test_published_form_cannot_be_published_again(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers, "Twice")
        _add_field(client, headers, form["id"], {"field_key": "x", "label": "X", "field_type": "text"})
        client.post(f"/api/forms/{form['id']}/publish", headers=headers)

        response = client.post(f"/api/forms/{form['id']}/publish", headers=headers)

        assert response.status_code == 409

    def test_archive_allowed_from_draft_and_published(self, client, db_session):
        headers = _admin(client, db_session)
        draft = _create_form(client, headers, "Draft arch")
        published = _create_form(client, headers, "Pub arch")
        _add_field(client, headers, published["id"], {"field_key": "x", "label": "X", "field_type": "text"})
        client.post(f"/api/forms/{published['id']}/publish", headers=headers)

        assert client.post(f"/api/forms/{draft['id']}/archive", headers=headers).status_code == 200
        assert client.post(f"/api/forms/{published['id']}/archive", headers=headers).status_code == 200

    def test_archived_form_cannot_be_archived_again(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers, "Already gone")
        client.post(f"/api/forms/{form['id']}/archive", headers=headers)

        response = client.post(f"/api/forms/{form['id']}/archive", headers=headers)

        assert response.status_code == 409

    def test_archived_form_cannot_be_edited_or_published(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers, "Gone")
        client.post(f"/api/forms/{form['id']}/archive", headers=headers)

        assert client.patch(
            f"/api/forms/{form['id']}", headers=headers, json={"name": "Zombie"}
        ).status_code == 409
        assert client.post(f"/api/forms/{form['id']}/publish", headers=headers).status_code == 409

    def test_only_draft_forms_can_be_deleted(self, client, db_session):
        headers = _admin(client, db_session)
        draft = _create_form(client, headers, "Deletable")
        published = _create_form(client, headers, "Protected")
        _add_field(client, headers, published["id"], {"field_key": "x", "label": "X", "field_type": "text"})
        client.post(f"/api/forms/{published['id']}/publish", headers=headers)

        assert client.delete(f"/api/forms/{published['id']}", headers=headers).status_code == 409
        assert client.delete(f"/api/forms/{draft['id']}", headers=headers).status_code == 204
        assert client.get(f"/api/forms/{draft['id']}", headers=headers).status_code == 404


class TestCreateField:
    def test_sort_order_auto_increments(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)

        first = _add_field(client, headers, form["id"], {"field_key": "a", "label": "A", "field_type": "text"})
        second = _add_field(client, headers, form["id"], {"field_key": "b", "label": "B", "field_type": "text"})

        assert first["sort_order"] == 0
        assert second["sort_order"] == 1

    def test_duplicate_field_key_rejected(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)
        _add_field(client, headers, form["id"], {"field_key": "a", "label": "A", "field_type": "text"})

        response = client.post(
            f"/api/forms/{form['id']}/fields",
            headers=headers,
            json={"field_key": "a", "label": "A again", "field_type": "text"},
        )

        assert response.status_code == 409

    def test_invalid_field_key_rejected(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)

        for bad in ("9abc", "UPPER", "has space", "has-dash", "abc!"):
            response = client.post(
                f"/api/forms/{form['id']}/fields",
                headers=headers,
                json={"field_key": bad, "label": "X", "field_type": "text"},
            )
            assert response.status_code == 422, bad

    def test_select_requires_options(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)

        response = client.post(
            f"/api/forms/{form['id']}/fields",
            headers=headers,
            json={"field_key": "grade", "label": "Grade", "field_type": "select"},
        )

        assert response.status_code == 422

    def test_select_options_are_stored(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)

        field = _add_field(client, headers, form["id"], {
            "field_key": "grade", "label": "Grade", "field_type": "select", "settings": SELECT_SETTINGS
        })

        assert field["settings"]["options"] == SELECT_SETTINGS["options"]

    def test_duplicate_option_values_rejected(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)

        response = client.post(
            f"/api/forms/{form['id']}/fields",
            headers=headers,
            json={
                "field_key": "grade",
                "label": "Grade",
                "field_type": "radio",
                "settings": {
                    "options": [
                        {"label": "A", "value": "a"},
                        {"label": "B", "value": "a"},
                    ]
                },
            },
        )

        assert response.status_code == 422

    def test_number_settings_validated(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)

        field = _add_field(client, headers, form["id"], {
            "field_key": "score",
            "label": "Score",
            "field_type": "number",
            "settings": {"min": 0, "max": 100, "step": 0.5},
        })
        assert field["settings"] == {"min": 0, "max": 100, "step": 0.5}

        response = client.post(
            f"/api/forms/{form['id']}/fields",
            headers=headers,
            json={"field_key": "bad", "label": "Bad", "field_type": "number", "settings": {"min": 10, "max": 5}},
        )
        assert response.status_code == 422

    def test_text_length_settings_validated(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)

        field = _add_field(client, headers, form["id"], {
            "field_key": "code",
            "label": "Code",
            "field_type": "text",
            "settings": {"min_length": 2, "max_length": 20},
        })
        assert field["settings"] == {"min_length": 2, "max_length": 20}

        response = client.post(
            f"/api/forms/{form['id']}/fields",
            headers=headers,
            json={"field_key": "bad", "label": "Bad", "field_type": "email", "settings": {"min_length": 5, "max_length": 2}},
        )
        assert response.status_code == 422

    def test_checkbox_settings_limited(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)

        field = _add_field(client, headers, form["id"], {
            "field_key": "agree",
            "label": "Agree",
            "field_type": "checkbox",
            "settings": {"checkbox_label": "I agree to the terms"},
        })
        assert field["settings"] == {"checkbox_label": "I agree to the terms"}

        response = client.post(
            f"/api/forms/{form['id']}/fields",
            headers=headers,
            json={
                "field_key": "bad",
                "label": "Bad",
                "field_type": "checkbox",
                "settings": {"min_length": 2},
            },
        )
        assert response.status_code == 422

    def test_fields_cannot_be_added_to_published_form(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)
        _add_field(client, headers, form["id"], {"field_key": "x", "label": "X", "field_type": "text"})
        client.post(f"/api/forms/{form['id']}/publish", headers=headers)

        response = client.post(
            f"/api/forms/{form['id']}/fields",
            headers=headers,
            json={"field_key": "y", "label": "Y", "field_type": "text"},
        )

        assert response.status_code == 409

    def test_field_on_unknown_form_returns_404(self, client, db_session):
        headers = _admin(client, db_session)
        response = client.post(
            "/api/forms/999999/fields",
            headers=headers,
            json={"field_key": "x", "label": "X", "field_type": "text"},
        )
        assert response.status_code == 404


class TestUpdateField:
    def test_rename_field(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)
        field = _add_field(client, headers, form["id"], {"field_key": "a", "label": "A", "field_type": "text"})

        response = client.patch(
            f"/api/forms/{form['id']}/fields/{field['id']}",
            headers=headers,
            json={"label": "Renamed", "field_key": "renamed"},
        )

        assert response.status_code == 200
        assert response.json()["label"] == "Renamed"
        assert response.json()["field_key"] == "renamed"

    def test_change_type_revalidates_settings(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)
        field = _add_field(client, headers, form["id"], {
            "field_key": "a", "label": "A", "field_type": "text", "settings": {"max_length": 20}
        })

        response = client.patch(
            f"/api/forms/{form['id']}/fields/{field['id']}",
            headers=headers,
            json={"field_type": "select"},
        )

        assert response.status_code == 422

    def test_change_type_with_valid_settings(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)
        field = _add_field(client, headers, form["id"], {
            "field_key": "a", "label": "A", "field_type": "text"
        })

        response = client.patch(
            f"/api/forms/{form['id']}/fields/{field['id']}",
            headers=headers,
            json={"field_type": "select", "settings": SELECT_SETTINGS},
        )

        assert response.status_code == 200
        assert response.json()["field_type"] == "select"

    def test_duplicate_key_on_rename_rejected(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)
        _add_field(client, headers, form["id"], {"field_key": "a", "label": "A", "field_type": "text"})
        field = _add_field(client, headers, form["id"], {"field_key": "b", "label": "B", "field_type": "text"})

        response = client.patch(
            f"/api/forms/{form['id']}/fields/{field['id']}",
            headers=headers,
            json={"field_key": "a"},
        )

        assert response.status_code == 409

    def test_update_field_on_published_form_rejected(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)
        field = _add_field(client, headers, form["id"], {"field_key": "a", "label": "A", "field_type": "text"})
        client.post(f"/api/forms/{form['id']}/publish", headers=headers)

        response = client.patch(
            f"/api/forms/{form['id']}/fields/{field['id']}",
            headers=headers,
            json={"label": "X"},
        )

        assert response.status_code == 409

    def test_update_unknown_field_returns_404(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)
        response = client.patch(
            f"/api/forms/{form['id']}/fields/999999", headers=headers, json={"label": "X"}
        )
        assert response.status_code == 404


class TestDeleteField:
    def test_delete_field(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)
        field = _add_field(client, headers, form["id"], {"field_key": "a", "label": "A", "field_type": "text"})

        response = client.delete(
            f"/api/forms/{form['id']}/fields/{field['id']}", headers=headers
        )

        assert response.status_code == 204
        assert db_session.scalar(
            select(FormField).where(FormField.id == field["id"])
        ) is None

    def test_delete_field_on_published_form_rejected(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)
        field = _add_field(client, headers, form["id"], {"field_key": "a", "label": "A", "field_type": "text"})
        client.post(f"/api/forms/{form['id']}/publish", headers=headers)

        response = client.delete(
            f"/api/forms/{form['id']}/fields/{field['id']}", headers=headers
        )

        assert response.status_code == 409


class TestReorderFields:
    def _form_with_three_fields(self, client, headers):
        form = _create_form(client, headers, "Reorderable")
        fields = []
        for key in ("a", "b", "c"):
            fields.append(
                _add_field(client, headers, form["id"], {"field_key": key, "label": key, "field_type": "text"})
            )
        return form, fields

    def test_reorder_applies_new_order(self, client, db_session):
        headers = _admin(client, db_session)
        form, fields = self._form_with_three_fields(client, headers)

        response = client.post(
            f"/api/forms/{form['id']}/fields/reorder",
            headers=headers,
            json={"field_ids": [fields[2]["id"], fields[0]["id"], fields[1]["id"]]},
        )

        assert response.status_code == 200
        order = [f["id"] for f in response.json()]
        assert order == [fields[2]["id"], fields[0]["id"], fields[1]["id"]]
        assert [f["field_key"] for f in response.json()] == ["c", "a", "b"]

    def test_reorder_missing_ids_rejected(self, client, db_session):
        headers = _admin(client, db_session)
        form, fields = self._form_with_three_fields(client, headers)

        response = client.post(
            f"/api/forms/{form['id']}/fields/reorder",
            headers=headers,
            json={"field_ids": [fields[0]["id"], fields[1]["id"]]},
        )

        assert response.status_code == 400

    def test_reorder_extra_ids_rejected(self, client, db_session):
        headers = _admin(client, db_session)
        form, fields = self._form_with_three_fields(client, headers)

        response = client.post(
            f"/api/forms/{form['id']}/fields/reorder",
            headers=headers,
            json={"field_ids": [fields[0]["id"], fields[1]["id"], fields[2]["id"], 12345]},
        )

        assert response.status_code == 400

    def test_reorder_duplicate_ids_rejected(self, client, db_session):
        headers = _admin(client, db_session)
        form, fields = self._form_with_three_fields(client, headers)

        response = client.post(
            f"/api/forms/{form['id']}/fields/reorder",
            headers=headers,
            json={"field_ids": [fields[0]["id"], fields[0]["id"], fields[1]["id"]]},
        )

        assert response.status_code == 400

    def test_reorder_on_published_form_rejected(self, client, db_session):
        headers = _admin(client, db_session)
        form, fields = self._form_with_three_fields(client, headers)
        client.post(f"/api/forms/{form['id']}/publish", headers=headers)

        response = client.post(
            f"/api/forms/{form['id']}/fields/reorder",
            headers=headers,
            json={"field_ids": [f["id"] for f in fields]},
        )

        assert response.status_code == 409


class TestFormsAndFieldsSecurity:
    def _operator_headers(self, client, db_session):
        create_user(db_session, "op", "op@example.com", role=Role.operator)
        return login_headers(client, "op")

    def _viewer_headers(self, client, db_session):
        create_user(db_session, "viewer", "viewer@example.com", role=Role.viewer)
        return login_headers(client, "viewer")

    def test_unauthenticated_requests_rejected(self, client, db_session):
        assert client.get("/api/forms").status_code == 401
        assert client.post("/api/forms", json={"name": "X"}).status_code == 401
        assert client.get("/api/forms/1").status_code == 401

    def test_operator_cannot_manage_forms(self, client, db_session):
        headers = self._operator_headers(client, db_session)
        form = _create_form(client, _admin(client, db_session))

        assert client.get("/api/forms", headers=headers).status_code == 403
        assert client.post("/api/forms", headers=headers, json={"name": "X"}).status_code == 403
        assert client.get(f"/api/forms/{form['id']}", headers=headers).status_code == 403
        assert client.post(f"/api/forms/{form['id']}/publish", headers=headers).status_code == 403

    def test_operator_cannot_manage_fields(self, client, db_session):
        headers = self._operator_headers(client, db_session)
        form = _create_form(client, _admin(client, db_session))

        assert client.post(
            f"/api/forms/{form['id']}/fields",
            headers=headers,
            json={"field_key": "x", "label": "X", "field_type": "text"},
        ).status_code == 403
        assert client.post(
            f"/api/forms/{form['id']}/fields/reorder", headers=headers, json={"field_ids": []}
        ).status_code == 403

    def test_viewer_cannot_manage_forms(self, client, db_session):
        headers = self._viewer_headers(client, db_session)
        assert client.get("/api/forms", headers=headers).status_code == 403


class TestFormsPersistToDatabase:
    def test_form_and_fields_persisted(self, client, db_session):
        headers = _admin(client, db_session)
        form_json = _create_form(client, headers, "Persisted")
        _add_field(client, headers, form_json["id"], {"field_key": "a", "label": "A", "field_type": "text"})

        form = db_session.scalar(select(Form).where(Form.id == form_json["id"]))
        assert form is not None
        assert form.status == "draft"
        assert len(form.fields) == 1
        assert form.fields[0].field_key == "a"

    def test_deleting_field_does_not_delete_form(self, client, db_session):
        headers = _admin(client, db_session)
        form = _create_form(client, headers)
        field = _add_field(client, headers, form["id"], {"field_key": "a", "label": "A", "field_type": "text"})
        client.delete(f"/api/forms/{form['id']}/fields/{field['id']}", headers=headers)

        assert db_session.scalar(select(Form).where(Form.id == form["id"])) is not None

    def test_any_user_row_can_be_owner_reference(self, client, db_session):
        """created_by stores the admin's id, who is a real user."""
        admin_user = create_user(
            db_session, "root", "root@example.com", password=ADMIN_PASSWORD, role=Role.admin
        )
        headers = login_headers(client, "root", ADMIN_PASSWORD)
        form_json = _create_form(client, headers)
        assert form_json["created_by"] == admin_user.id
        assert isinstance(admin_user, User)