"""Phase 6 record export endpoint tests (CSV / XLSX / PDF / SQL).

Covers the generic ``GET /api/forms/{form_id}/submissions/export`` surface:

* authorization (admin / operator / viewer / anonymous / draft / archived)
* format validation (csv, xlsx, pdf, sql; unsupported -> 400)
* reuse of the Phase 5 query engine (search, filters, sort) with identical
  semantics to the records list
* export ignoring the Records page ``limit`` / ``offset``
* dynamic columns driven by ``FormField.sort_order`` with labels as headers
* missing fields exported as blank values; unknown stored keys never become
  arbitrary columns
* CSV escaping (commas, quotes, newlines, Unicode, empty values)
* valid .xlsx with a single ``Records`` worksheet and native values
* valid PDF with form name / headers / long-text robustness
* SQL structure, safe JSON serialization, and SQL-injection resistance
* the hard export record limit (no silent truncation)
"""

import base64
import csv
import io
import json
import re
import zlib
from urllib.parse import urlencode

import openpyxl
from sqlalchemy import select

from app.models import Role, Submission, User
from app.services import export_service

from .conftest import create_user
from .test_records import (
    _admin,
    _create_form,
    _headers,
    _submit,
    VALID_EMPLOYEE_DATA,
)

SELECT_OPTIONS = [
    {"label": "Engineering", "value": "eng"},
    {"label": "Sales", "value": "sales"},
]

EXPORT_FIELDS = [
    {"field_key": "full_name", "label": "Full Name", "field_type": "text", "required": True},
    {"field_key": "title", "label": "Job Title", "field_type": "text"},
    {
        "field_key": "department",
        "label": "Department",
        "field_type": "select",
        "required": True,
        "settings": {"options": SELECT_OPTIONS},
    },
    {"field_key": "email", "label": "Email", "field_type": "email"},
    {"field_key": "years", "label": "Years", "field_type": "number"},
    {"field_key": "hired", "label": "Hiring Date", "field_type": "date"},
    {"field_key": "shift", "label": "Shift Start", "field_type": "time"},
    {"field_key": "interview", "label": "Interview Date", "field_type": "datetime"},
    {"field_key": "notes", "label": "Notes", "field_type": "textarea"},
    {"field_key": "agree", "label": "Agreed", "field_type": "checkbox"},
]

RWANDA = "Munyaneza Karangwa"

RECORD_ONE = {
    "full_name": "Rahul Ahirwar",
    "title": "Lead Engineer",
    "department": "eng",
    "email": "rahul@example.com",
    "years": 30,
    "hired": "2024-05-12",
    "shift": "09:30",
    "interview": "2025-01-15T10:00:00",
    "notes": "Lead, \"quoted\": note\nsecond line",
    "agree": True,
}

RECORD_TWO = {
    "full_name": "Priya Sharma",
    "title": "Sales Lead",
    "department": "sales",
    "email": "priya@example.com",
    "years": 25,
    "hired": "2025-03-01",
    "shift": "14:00",
    "interview": "2025-02-10T16:30:00",
    "notes": "Plain note",
    "agree": True,
}

RECORD_THREE = {
    "full_name": RWANDA,
    "title": None,
    "department": "eng",
    "years": 40,
    "hired": "2021-11-20",
    "shift": "10:45",
    "interview": "2025-03-05T08:15:00",
    "agree": False,
}

HEADERS = [
    "ID",
    "Submitted By",
    "Submitted At",
    "Full Name",
    "Job Title",
    "Department",
    "Email",
    "Years",
    "Hiring Date",
    "Shift Start",
    "Interview Date",
    "Notes",
    "Agreed",
]


def _export(client, headers, form_id, **params):
    query = urlencode(params, doseq=True)
    return client.get(f"/api/forms/{form_id}/submissions/export?{query}", headers=headers)


def _seed(client, headers, form_id, records=None):
    created = []
    for record in (records or [RECORD_ONE, RECORD_TWO, RECORD_THREE]):
        created.append(_submit(client, headers, form_id, record))
    return created


def _csv_rows(content: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))


def _pdf_text(content: bytes) -> str:
    """Decompress PDF content streams so drawn text can be searched."""
    chunks: list[bytes] = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", content, re.DOTALL):
        raw = match.group(1).rstrip(b"\r\n")
        decoded = None
        try:
            decoded = base64.a85decode(raw, adobe=True)
        except Exception:
            pass
        for candidate in (([decoded] if decoded else []) + [raw]):
            try:
                chunks.append(zlib.decompress(candidate))
                break
            except zlib.error:
                chunks.append(candidate)
    return b"".join(chunks).decode("latin-1", errors="replace")


def _rich_form(client, headers, status="published"):
    return _create_form(client, headers, name="Employee Onboarding", fields=EXPORT_FIELDS, status=status)


class TestExportAuthorization:
    def test_anonymous_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        response = _export(client, {}, form_id, format="csv")

        assert response.status_code == 401

    def test_all_roles_can_export(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        operator = _headers(client, db_session, "operator", Role.operator)
        viewer = _headers(client, db_session, "viewer", Role.viewer)

        for headers in (admin, operator, viewer):
            response = _export(client, headers, form_id, format="csv")
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/csv")

    def test_draft_form_not_exportable(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin, status="draft")

        response = _export(client, admin, form_id, format="csv")

        assert response.status_code == 400

    def test_archived_form_exportable(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)
        result = client.post(f"/api/forms/{form_id}/archive", headers=admin)
        assert result.status_code == 200

        response = _export(client, admin, form_id, format="csv")

        assert response.status_code == 200
        assert len(_csv_rows(response.content)) == 4

    def test_content_disposition_present(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="csv")

        disposition = response.headers["content-disposition"]
        assert disposition.startswith("attachment; filename=")
        assert "employee-onboarding-records.csv" in disposition


class TestExportFormatValidation:
    def test_unsupported_format_400(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="xml")

        assert response.status_code == 400
        assert "Unsupported export format" in response.json()["detail"]

    def test_all_supported_formats_return_files(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        expected = {
            "csv": "text/csv",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "pdf": "application/pdf",
            "sql": "application/sql",
        }
        for export_format, media_type in expected.items():
            response = _export(client, admin, form_id, format=export_format)
            assert response.status_code == 200
            assert response.headers["content-type"].startswith(media_type)
            assert response.content


class TestExportQuerySemantics:
    def test_search_reduces_rows(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="csv", search="rahul")

        rows = _csv_rows(response.content)
        assert len(rows) == 2  # header + 1 match
        assert rows[1][3] == "Rahul Ahirwar"

    def test_search_is_case_insensitive(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="csv", search="PRIYA")

        rows = _csv_rows(response.content)
        assert len(rows) == 2

    def test_filter_reduces_rows(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        filters = json.dumps([{"field": "department", "operator": "equals", "value": "eng"}])
        response = _export(client, admin, form_id, format="csv", filters=filters)

        rows = _csv_rows(response.content)
        assert len(rows) == 3  # header + 2 matches

    def test_multiple_filters_are_and_combined(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        filters = json.dumps([
            {"field": "department", "operator": "equals", "value": "eng"},
            {"field": "years", "operator": "greater_than", "value": 35},
        ])
        response = _export(client, admin, form_id, format="csv", filters=filters)

        rows = _csv_rows(response.content)
        assert len(rows) == 2  # header + exactly one match
        assert rows[1][3] == RWANDA

    def test_filter_number_between(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        filters = json.dumps([{"field": "years", "operator": "between", "value": [26, 40]}])
        response = _export(client, admin, form_id, format="csv", filters=filters)

        rows = _csv_rows(response.content)
        assert len(rows) == 3  # header + 2 matches

    def test_filter_temporal(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        filters = json.dumps([{"field": "hired", "operator": "after", "value": "2024-12-31"}])
        response = _export(client, admin, form_id, format="csv", filters=filters)

        rows = _csv_rows(response.content)
        assert len(rows) == 2  # header + only Priya (2025-03-01)
        assert rows[1][3] == "Priya Sharma"

    def test_export_ignores_page_offset(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        for index in range(12):
            _submit(client, admin, form_id, {**VALID_EMPLOYEE_DATA, "years": 20 + index})

        response = _export(client, admin, form_id, format="csv")

        rows = _csv_rows(response.content)
        assert len(rows) == 13  # header + all 12 matching records

    def test_export_ignores_limit_offset_params(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        for index in range(7):
            _submit(client, admin, form_id, {**VALID_EMPLOYEE_DATA, "years": 20 + index})

        response = _export(
            client,
            admin,
            form_id,
            format="csv",
            limit=2,
            offset=4,
        )

        rows = _csv_rows(response.content)
        assert len(rows) == 8  # limit/offset are not applied to exports

    def test_sort_asc(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="csv", sort_by="years", sort_order="asc")

        rows = _csv_rows(response.content)[1:]
        assert [row[7] for row in rows] == ["25", "30", "40"]

    def test_sort_desc(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="csv", sort_by="years", sort_order="desc")

        rows = _csv_rows(response.content)[1:]
        assert [row[7] for row in rows] == ["40", "30", "25"]

    def test_invalid_query_returns_400(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        bad_filter = _export(
            client, admin, form_id, format="csv",
            filters=json.dumps([{"field": "nope", "operator": "equals", "value": 1}]),
        )
        assert bad_filter.status_code == 400

        bad_sort = _export(client, admin, form_id, format="csv", sort_by="years", sort_order="sideways")
        assert bad_sort.status_code == 400


class TestExportColumns:
    def test_header_order_and_labels(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="csv")

        rows = _csv_rows(response.content)
        assert rows[0] == HEADERS

    def test_missing_field_values_are_blank(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _submit(client, admin, form_id, {
            "full_name": "Minimal",
            "department": "sales",
            "agree": True,
        })

        response = _export(client, admin, form_id, format="csv")

        rows = _csv_rows(response.content)
        row = rows[1]
        assert row[4] == ""  # Job Title
        assert row[6] == ""  # Email
        assert row[7] == ""  # Years
        assert row[8] == ""  # Hiring Date
        assert row[9] == ""  # Shift Start
        assert row[10] == ""  # Interview Date

    def test_unknown_stored_fields_are_not_columns(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        root = db_session.scalar(select(User).where(User.username == "root"))
        db_session.add(Submission(
            form_id=form_id,
            submitted_by=root.id,
            data={"full_name": "Stray", "department": "eng", "secret_key": "zzz", "mystery": True},
        ))
        db_session.commit()

        response = _export(client, admin, form_id, format="csv")

        rows = _csv_rows(response.content)
        assert rows[0] == HEADERS  # no secret_key / mystery columns
        assert all("secret_key" not in row and "mystery" not in row for row in rows)

    def test_unicode_preserved(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="csv")

        rows = _csv_rows(response.content)
        names = {row[3] for row in rows[1:]}
        assert RWANDA in names


class TestCsvContent:
    def test_escaping_commas_quotes_newlines(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="csv")

        rows = _csv_rows(response.content)
        by_name = {row[3]: row for row in rows[1:]}
        assert by_name["Rahul Ahirwar"][11] == 'Lead, "quoted": note\nsecond line'

    def test_booleans_and_choices_are_display_values(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="csv")

        rows = {row[3]: row for row in _csv_rows(response.content)[1:]}
        assert rows["Rahul Ahirwar"][5] == "Engineering"  # select -> label
        assert rows["Rahul Ahirwar"][12] == "Yes"  # checkbox
        assert rows[RWANDA][12] == "No"

    def test_empty_export_header_only(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)

        response = _export(client, admin, form_id, format="csv")

        rows = _csv_rows(response.content)
        assert rows == [HEADERS]


class TestExcelContent:
    def test_xlsx_is_valid_with_records_worksheet(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="xlsx")

        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        assert workbook.sheetnames == ["Records"]
        worksheet = workbook["Records"]
        headers = [cell.value for cell in worksheet[1]]
        assert headers == HEADERS
        assert worksheet.max_row == 4

    def test_xlsx_values_and_unicode(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="xlsx")

        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        worksheet = workbook["Records"]
        by_name = {}
        for row in worksheet.iter_rows(min_row=2, values_only=True):
            by_name[row[3]] = row
        rahul = by_name["Rahul Ahirwar"]
        assert rahul[5] == "Engineering"  # select -> label
        assert rahul[7] == 30  # native numeric
        assert rahul[12] == "Yes"  # checkbox display
        assert by_name[RWANDA][12] == "No"

    def test_xlsx_missing_fields_are_empty(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _submit(client, admin, form_id, {"full_name": "Minimal", "department": "sales", "agree": True})

        response = _export(client, admin, form_id, format="xlsx")

        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        worksheet = workbook["Records"]
        row = [cell.value for cell in worksheet[2]]
        assert row[6] is None  # Email
        assert row[7] is None  # Years
        assert row[8] is None  # Hiring Date


class TestPdfContent:
    def test_pdf_is_valid_and_contains_content(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="pdf")

        assert response.content.startswith(b"%PDF")
        text = _pdf_text(response.content)
        assert "Employee Onboarding" in text
        assert "Full Name" in text
        assert "Department" in text
        assert "Rahul" in text

    def test_pdf_long_text_wraps_without_crashing(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _submit(client, admin, form_id, {**RECORD_ONE, "notes": "x" * 4000})

        response = _export(client, admin, form_id, format="pdf")

        assert response.status_code == 200
        assert response.content.startswith(b"%PDF")
        # The PDF renderer caps a single unwrappable cell so the export never
        # aborts with a reportlab LayoutError; full data lives in CSV/XLSX/SQL.
        # The 4000-character value is clipped to ~397 characters in the PDF.
        assert _pdf_text(response.content).count("x") <= 400


class TestSqlContent:
    def test_sql_structure(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="sql")

        text = response.content.decode("utf-8")
        assert "INSERT INTO submissions (form_id, submitted_by, data, submitted_at)" in text
        assert "::jsonb" in text
        assert "VALUES" in text
        assert "COMMIT;" in text
        assert "SET standard_conforming_strings = on;" in text

    def test_sql_injection_value_is_data(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        attack = "'); DROP TABLE submissions; --"
        _submit(client, admin, form_id, {**RECORD_ONE, "notes": attack})

        response = _export(client, admin, form_id, format="sql")

        text = response.content.decode("utf-8")
        # The doubled single quote keeps the attacker's string inside the literal.
        assert "''); DROP TABLE submissions; --" in text
        assert text.count("DROP TABLE submissions") == 1
        assert text.strip().endswith("COMMIT;")

    def test_sql_json_safe_with_special_characters(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _submit(client, admin, form_id, {
            **RECORD_TWO,
            "notes": "It's \"quoted\"\nnewline\ttab ← unicode",
        })

        response = _export(client, admin, form_id, format="sql")

        text = response.content.decode("utf-8")
        assert "It''s" in text
        assert "unicode" in text

    def test_sql_never_leaks_credentials(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="sql")

        text = response.content.decode("utf-8")
        assert "password_hash" not in text
        assert "access_token" not in text
        assert "jwt" not in text.lower()


class TestExportLimit:
    def test_over_limit_returns_400_without_truncation(self, client, db_session, monkeypatch):
        monkeypatch.setattr(export_service, "MAX_EXPORT_RECORDS", 3)
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        for index in range(5):
            _submit(client, admin, form_id, {**VALID_EMPLOYEE_DATA, "years": 20 + index})

        response = _export(client, admin, form_id, format="csv")

        assert response.status_code == 400
        assert "Export is limited to 3 records" in response.json()["detail"]

    def test_limit_applies_to_all_formats(self, client, db_session, monkeypatch):
        monkeypatch.setattr(export_service, "MAX_EXPORT_RECORDS", 2)
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        for index in range(4):
            _submit(client, admin, form_id, {**VALID_EMPLOYEE_DATA, "years": 20 + index})

        for export_format in ("csv", "xlsx", "pdf", "sql"):
            response = _export(client, admin, form_id, format=export_format)
            assert response.status_code == 400

    def test_under_limit_succeeds(self, client, db_session, monkeypatch):
        monkeypatch.setattr(export_service, "MAX_EXPORT_RECORDS", 10)
        admin = _admin(client, db_session)
        form_id = _rich_form(client, admin)
        for index in range(5):
            _submit(client, admin, form_id, {**VALID_EMPLOYEE_DATA, "years": 20 + index})

        response = _export(client, admin, form_id, format="csv")

        assert response.status_code == 200
        rows = _csv_rows(response.content)
        assert len(rows) == 6  # header + 5