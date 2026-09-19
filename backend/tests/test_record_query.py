"""Phase 5 search / filter / sort / pagination endpoint tests.

Covers the generic record querying surface added to
``GET /api/forms/{form_id}/submissions``:

* free-text search across text-like fields (case-insensitive substring)
* dynamic per-type filters (text, number, date, time, datetime, select,
  radio, checkbox) with the exact operator sets per type
* sorting (``sort_by`` + ``sort_order``) with deterministic tie-breakers
* filtered ``total`` combined with ``limit`` / ``offset`` pagination
* 400 validation for malformed filters, unknown fields/operators, invalid
  option values, and bad sort parameters
* role enforcement (admin / operator / viewer allowed; anonymous rejected)
* cross-form isolation preserved when querying
"""

import json

from app.models import Role

from .conftest import create_user
from .test_records import (
    _admin,
    _create_form,
    _headers,
    _list,
    _submit,
    VALID_EMPLOYEE_DATA,
)

SELECT_OPTIONS = [
    {"label": "Engineering", "value": "eng"},
    {"label": "Sales", "value": "sales"},
]

RICH_FIELDS = [
    {"field_key": "full_name", "label": "Full Name", "field_type": "text", "required": True},
    {
        "field_key": "department",
        "label": "Department",
        "field_type": "select",
        "required": True,
        "settings": {"options": SELECT_OPTIONS},
    },
    {"field_key": "email", "label": "Email", "field_type": "email"},
    {"field_key": "years", "label": "Years", "field_type": "number"},
    {"field_key": "hired", "label": "Hired", "field_type": "date"},
    {"field_key": "shift", "label": "Shift", "field_type": "time"},
    {"field_key": "interview", "label": "Interview", "field_type": "datetime"},
    {"field_key": "notes", "label": "Notes", "field_type": "textarea"},
    {"field_key": "agree", "label": "Agree", "field_type": "checkbox"},
]


def _rich_form(client, headers):
    return _create_form(client, headers, name="Census", fields=RICH_FIELDS)


def _load(client, headers, form_id, **params):
    return _list(client, headers, form_id, **params)


def _ids(body):
    return [item["id"] for item in body["items"]]


class TestSearch:
    def _seed(self, client, headers, form_id):
        _submit(client, headers, form_id, {
            "full_name": "Rahul Ahirwar",
            "department": "eng",
            "email": "rahul@example.com",
            "years": 30,
            "hired": "2024-05-12",
            "shift": "09:30",
            "interview": "2025-01-15T10:00:00",
            "notes": "Lead engineer",
            "agree": True,
        })
        _submit(client, headers, form_id, {
            "full_name": "Priya Sharma",
            "department": "sales",
            "email": "priya@example.com",
            "years": 25,
            "hired": "2025-03-01",
            "shift": "14:00",
            "interview": "2025-02-10T16:30:00",
            "notes": "Sales lead",
            "agree": True,
        })
        _submit(client, headers, form_id, {
            "full_name": "Amit Patel",
            "department": "eng",
            "email": "amit@example.com",
            "years": 40,
            "hired": "2021-11-20",
            "shift": "10:45",
            "interview": "2025-03-05T08:15:00",
            "notes": "Senior engineer",
            "agree": False,
        })

    def test_case_insensitive_substring(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = _load(client, admin, form_id, search="rahul").json()

        assert body["total"] == 1
        assert body["items"][0]["data"]["full_name"] == "Rahul Ahirwar"

    def test_search_matches_any_searchable_field(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = _load(client, admin, form_id, search="lead").json()

        assert body["total"] == 2

    def test_search_ignores_numbers_and_dates(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        for term in ("30", "2024", "09:30", "TRUE"):
            assert _load(client, admin, form_id, search=term).json()["total"] == 0

    def test_search_blank_returns_all(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        assert _load(client, admin, form_id, search="   ").json()["total"] == 3

    def test_search_unknown_term_returns_empty(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = _load(client, admin, form_id, search="zzzz").json()

        assert body["total"] == 0
        assert body["items"] == []

    def test_search_injected_patterns_are_literal(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = _load(client, admin, form_id, search="' OR 1=1 --").json()

        assert body["total"] == 0

    def test_search_select_matches_stored_values(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = _load(client, admin, form_id, search="eng").json()

        assert body["total"] == 2


class TestNumberFilters:
    def _seed(self, client, headers, form_id):
        _submit(client, headers, form_id, {**VALID_EMPLOYEE_DATA, "years": 18})
        _submit(client, headers, form_id, {**VALID_EMPLOYEE_DATA, "years": "25"})
        _submit(client, headers, form_id, {**VALID_EMPLOYEE_DATA, "years": 60})

    def _filtered(self, client, headers, form_id, operator, value):
        return _load(
            client,
            headers,
            form_id,
            filters=json.dumps([{"field": "years", "operator": operator, "value": value}]),
        ).json()

    def test_equals_matches_numeric_and_string_storage(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "equals", 25)

        assert body["total"] == 1
        assert body["items"][0]["data"]["years"] == "25"

    def test_not_equals(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "not_equals", 25)

        assert body["total"] == 2

    def test_greater_than(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "greater_than", 25)

        assert body["total"] == 1
        assert body["items"][0]["data"]["years"] == 60

    def test_greater_than_or_equal(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "greater_than_or_equal", 25)

        assert body["total"] == 2

    def test_less_than(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "less_than", 25)

        assert body["total"] == 1

    def test_less_than_or_equal(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "less_than_or_equal", 25)

        assert body["total"] == 2

    def test_between_inclusive(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "between", [18, 25])

        assert body["total"] == 2


class TestTextFilters:
    def _seed(self, client, headers, form_id):
        _submit(client, headers, form_id, {**VALID_EMPLOYEE_DATA, "full_name": "Alpha Rahman"})
        _submit(client, headers, form_id, {**VALID_EMPLOYEE_DATA, "full_name": "Beta Power"})
        _submit(client, headers, form_id, {**VALID_EMPLOYEE_DATA, "full_name": "Gamma Rahman"})

    def _filtered(self, client, headers, form_id, operator, value):
        return _load(
            client,
            headers,
            form_id,
            filters=json.dumps(
                [{"field": "full_name", "operator": operator, "value": value}]
            ),
        ).json()

    def test_equals_case_insensitive(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "equals", "alpha rahman")

        assert body["total"] == 1

    def test_contains(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "contains", "rah")

        assert body["total"] == 2

    def test_starts_with(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "starts_with", "beta")

        assert body["total"] == 1

    def test_ends_with(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "ends_with", "POWER")

        assert body["total"] == 1


class TestTemporalFilters:
    def _seed(self, client, headers, form_id):
        _submit(client, headers, form_id, {
            "full_name": "One",
            "department": "eng",
            "hired": "2024-05-12",
            "shift": "09:30",
            "interview": "2025-01-15T10:00:00",
            "agree": True,
        })
        _submit(client, headers, form_id, {
            "full_name": "Two",
            "department": "eng",
            "hired": "2025-03-01",
            "shift": "14:00",
            "interview": "2025-02-10T16:30:00",
            "agree": True,
        })

    def _filtered(self, client, headers, form_id, field, operator, value):
        return _load(
            client,
            headers,
            form_id,
            filters=json.dumps([{"field": field, "operator": operator, "value": value}]),
        ).json()

    def test_date_before(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "hired", "before", "2025-01-01")

        assert body["total"] == 1

    def test_date_after_on_or_after(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "hired", "after", "2025-01-01")

        assert body["total"] == 1

        boundary = self._filtered(client, admin, form_id, "hired", "on_or_after", "2025-03-01")

        assert boundary["total"] == 1

    def test_date_on_or_before(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "hired", "on_or_before", "2024-05-12")

        assert body["total"] == 1

    def test_date_between(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "hired", "between", ["2024-01-01", "2025-02-01"])

        assert body["total"] == 1

    def test_time_after_and_equals(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "shift", "after", "12:00")

        assert body["total"] == 1
        assert body["items"][0]["data"]["shift"] == "14:00"

    def test_time_equals_matches_seconds_storage(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _submit(client, admin, form_id, {
            "full_name": "One",
            "department": "eng",
            "shift": "09:30:00",
            "agree": True,
        })
        _submit(client, admin, form_id, {
            "full_name": "Two",
            "department": "eng",
            "shift": "09:30",
            "agree": True,
        })

        body = self._filtered(client, admin, form_id, "shift", "equals", "09:30")

        assert body["total"] == 2

    def test_time_between(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "shift", "between", ["09:00", "12:00"])

        assert body["total"] == 1

    def test_datetime_operators(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        before = self._filtered(
            client, admin, form_id, "interview", "before", "2025-02-01T00:00:00"
        )
        assert before["total"] == 1

        on_or_after = self._filtered(
            client, admin, form_id, "interview", "on_or_after", "2025-02-10T16:30:00"
        )
        assert on_or_after["total"] == 1

        equals = self._filtered(
            client, admin, form_id, "interview", "equals", "2025-01-15T10:00:00"
        )
        assert equals["total"] == 1

        between = self._filtered(
            client,
            admin,
            form_id,
            "interview",
            "between",
            ["2025-01-01T00:00:00", "2025-01-31T23:59:59"],
        )
        assert between["total"] == 1


class TestChoiceFilters:
    def _seed(self, client, headers, form_id):
        _submit(client, headers, form_id, {
            "full_name": "A",
            "department": "eng",
            "agree": True,
        })
        _submit(client, headers, form_id, {
            "full_name": "B",
            "department": "Sales",
            "agree": True,
        })
        _submit(client, headers, form_id, {
            "full_name": "C",
            "department": "eng",
            "agree": True,
        })

    def _filtered(self, client, headers, form_id, operator, value):
        return _load(
            client,
            headers,
            form_id,
            filters=json.dumps(
                [{"field": "department", "operator": operator, "value": value}]
            ),
        ).json()

    def test_equals_by_value(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "equals", "eng")

        assert body["total"] == 2

    def test_equals_by_label(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "equals", "Engineering")

        assert body["total"] == 2

    def test_equals_matches_label_stored_as_value(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "equals", "Sales")

        assert body["total"] == 1

    def test_not_equals(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = self._filtered(client, admin, form_id, "not_equals", "eng")

        assert body["total"] == 1


class TestCheckboxFilters:
    def _seed(self, client, headers, form_id):
        _submit(client, headers, form_id, {**VALID_EMPLOYEE_DATA, "agree": True})
        _submit(client, headers, form_id, {**VALID_EMPLOYEE_DATA, "agree": False})

    def test_equals_true(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = _load(
            client,
            admin,
            form_id,
            filters=json.dumps([{"field": "agree", "operator": "equals", "value": True}]),
        ).json()

        assert body["total"] == 1
        assert body["items"][0]["data"]["agree"] is True

    def test_equals_false(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = _load(
            client,
            admin,
            form_id,
            filters=json.dumps([{"field": "agree", "operator": "equals", "value": False}]),
        ).json()

        assert body["total"] == 1
        assert body["items"][0]["data"]["agree"] is False


class TestCombinedFilters:
    def _seed(self, client, headers, form_id):
        _submit(client, headers, form_id, {
            "full_name": "Rahul A",
            "department": "eng",
            "years": 30,
            "agree": True,
        })
        _submit(client, headers, form_id, {
            "full_name": "Rahul B",
            "department": "eng",
            "years": 18,
            "agree": True,
        })
        _submit(client, headers, form_id, {
            "full_name": "Rahul C",
            "department": "sales",
            "years": 40,
            "agree": True,
        })

    def test_multiple_filters_are_and_combined(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = _load(
            client,
            admin,
            form_id,
            filters=json.dumps([
                {"field": "department", "operator": "equals", "value": "eng"},
                {"field": "years", "operator": "greater_than", "value": 20},
            ]),
        ).json()

        assert body["total"] == 1
        assert body["items"][0]["data"]["full_name"] == "Rahul A"

    def test_search_and_filter_combine(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = _load(
            client,
            admin,
            form_id,
            search="rahul",
            filters=json.dumps([{"field": "department", "operator": "equals", "value": "eng"}]),
        ).json()

        assert body["total"] == 2


class TestSorting:
    def _seed(self, client, headers, form_id):
        _submit(client, headers, form_id, {**VALID_EMPLOYEE_DATA, "full_name": "Charlie", "years": 30})
        _submit(client, headers, form_id, {**VALID_EMPLOYEE_DATA, "full_name": "Alpha", "years": 18})
        _submit(client, headers, form_id, {**VALID_EMPLOYEE_DATA, "full_name": "Beta", "years": 45})

    def test_sort_numeric_asc(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = _load(client, admin, form_id, sort_by="years", sort_order="asc").json()

        assert [item["data"]["years"] for item in body["items"]] == [18, 30, 45]

    def test_sort_numeric_desc(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = _load(client, admin, form_id, sort_by="years", sort_order="desc").json()

        assert [item["data"]["years"] for item in body["items"]] == [45, 30, 18]

    def test_sort_text(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = _load(client, admin, form_id, sort_by="full_name", sort_order="asc").json()

        assert [item["data"]["full_name"] for item in body["items"]] == [
            "Alpha",
            "Beta",
            "Charlie",
        ]

    def test_sort_default_order_newest_first(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = _load(client, admin, form_id).json()

        ids = _ids(body)
        assert ids == sorted(ids, reverse=True)

    def test_sort_by_date(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _submit(client, admin, form_id, {
            "full_name": "A", "department": "eng", "hired": "2024-05-12", "agree": True,
        })
        _submit(client, admin, form_id, {
            "full_name": "B", "department": "eng", "hired": "2025-03-01", "agree": True,
        })

        body = _load(client, admin, form_id, sort_by="hired", sort_order="asc").json()

        assert [item["data"]["full_name"] for item in body["items"]] == ["A", "B"]

    def test_sort_by_datetime(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _submit(client, admin, form_id, {
            "full_name": "A", "department": "eng",
            "interview": "2025-02-10T16:30:00", "agree": True,
        })
        _submit(client, admin, form_id, {
            "full_name": "B", "department": "eng",
            "interview": "2025-01-15T10:00:00", "agree": True,
        })

        body = _load(client, admin, form_id, sort_by="interview", sort_order="asc").json()

        assert [item["data"]["full_name"] for item in body["items"]] == ["B", "A"]

    def test_sort_by_missing_key_pushes_to_end(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _submit(client, admin, form_id, {**VALID_EMPLOYEE_DATA, "full_name": "A"})
        _submit(client, admin, form_id, {**VALID_EMPLOYEE_DATA, "full_name": "B", "years": 5})

        body = _load(client, admin, form_id, sort_by="years", sort_order="desc").json()

        assert [item["data"].get("years") for item in body["items"]] == [5, None]


class TestPaginationWithQuery:
    def _seed(self, client, headers, form_id):
        for name in ("Alpha", "Bravo", "Charlie", "Delta", "Echo"):
            _submit(client, headers, form_id, {**VALID_EMPLOYEE_DATA, "full_name": name, "years": 20})

    def test_total_reflects_filters(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)
        _submit(client, admin, form_id, {**VALID_EMPLOYEE_DATA, "full_name": "Zulu", "years": 60})

        body = _load(
            client,
            admin,
            form_id,
            limit=2,
            offset=0,
            filters=json.dumps([{"field": "years", "operator": "equals", "value": 20}]),
        ).json()

        assert body["total"] == 5
        assert len(body["items"]) == 2

    def test_page_boundaries_with_filters(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)
        _submit(client, admin, form_id, {**VALID_EMPLOYEE_DATA, "full_name": "Zulu", "years": 60})

        filters = json.dumps([{"field": "years", "operator": "equals", "value": 20}])
        page1 = _load(client, admin, form_id, limit=3, offset=0, filters=filters).json()
        page2 = _load(client, admin, form_id, limit=3, offset=3, filters=filters).json()

        assert len(page1["items"]) == 3 and len(page2["items"]) == 2
        assert page1["total"] == 5 and page2["total"] == 5
        assert not set(_ids(page1)) & set(_ids(page2))

    def test_sort_combined_with_pagination(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        body = _load(
            client, admin, form_id, limit=2, offset=0, sort_by="years", sort_order="desc"
        ).json()

        assert body["total"] == 5
        assert len(body["items"]) == 2


class TestQueryValidation:
    def _seed(self, client, headers, form_id):
        _submit(client, headers, form_id, VALID_EMPLOYEE_DATA)

    def test_unknown_field_400(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        response = _load(
            client,
            admin,
            form_id,
            filters=json.dumps([{"field": "nope", "operator": "equals", "value": 1}]),
        )

        assert response.status_code == 400

    def test_invalid_operator_for_type_400(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        response = _load(
            client,
            admin,
            form_id,
            filters=json.dumps([{"field": "years", "operator": "contains", "value": 1}]),
        )

        assert response.status_code == 400

    def test_invalid_option_400(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        response = _load(
            client,
            admin,
            form_id,
            filters=json.dumps([{"field": "department", "operator": "equals", "value": "bogus"}]),
        )

        assert response.status_code == 400

    def test_invalid_number_400(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        response = _load(
            client,
            admin,
            form_id,
            filters=json.dumps([{"field": "years", "operator": "equals", "value": "abc"}]),
        )

        assert response.status_code == 400

    def test_malformed_filters_json_400(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        response = _load(client, admin, form_id, filters="not-json")

        assert response.status_code == 400

    def test_filters_not_array_400(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        response = _load(client, admin, form_id, filters='{"field":"years"}')

        assert response.status_code == 400

    def test_filter_missing_value_400(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        response = _load(
            client,
            admin,
            form_id,
            filters=json.dumps([{"field": "years", "operator": "equals"}]),
        )

        assert response.status_code == 400

    def test_between_wrong_shape_400(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        response = _load(
            client,
            admin,
            form_id,
            filters=json.dumps([{"field": "years", "operator": "between", "value": 5}]),
        )

        assert response.status_code == 400

    def test_bad_sort_order_400(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        response = _load(client, admin, form_id, sort_by="years", sort_order="sideways")

        assert response.status_code == 400

    def test_unknown_sort_field_400(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        self._seed(client, admin, form_id)

        response = _load(client, admin, form_id, sort_by="zzz")

        assert response.status_code == 400


class TestQuerySecurity:
    def test_anonymous_rejected_with_query(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)

        response = _load(client, {}, form_id, search="rah")

        assert response.status_code == 401

    def test_all_roles_can_query(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)
        operator = _headers(client, db_session, "operator", Role.operator)
        viewer = _headers(client, db_session, "viewer", Role.viewer)

        filters = json.dumps([{"field": "full_name", "operator": "contains", "value": "rah"}])

        assert _load(client, admin, form_id, search="rah").status_code == 200
        assert _load(client, operator, form_id, filters=filters).status_code == 200
        assert _load(client, viewer, form_id, sort_by="full_name").status_code == 200

    def test_query_does_not_leak_across_forms(self, client, db_session):
        admin = _admin(client, db_session)
        form_a = _rich_form(client, admin)
        form_b = _create_form(client, admin, name="Other", fields=RICH_FIELDS)
        _submit(client, admin, form_a, {**VALID_EMPLOYEE_DATA, "full_name": "Alpha"})
        _submit(client, admin, form_b, {**VALID_EMPLOYEE_DATA, "full_name": "Alpha"})

        body = _load(
            client,
            admin,
            form_a,
            filters=json.dumps([{"field": "full_name", "operator": "equals", "value": "Alpha"}]),
        ).json()

        assert body["total"] == 1
        assert all(item["form_id"] == form_a for item in body["items"])

    def test_query_works_on_archived_forms(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _submit(client, admin, form_id, VALID_EMPLOYEE_DATA)
        assert client.post(f"/api/forms/{form_id}/archive", headers=admin).status_code == 200

        body = _load(client, admin, form_id, search="rah").json()

        assert body["total"] == 1