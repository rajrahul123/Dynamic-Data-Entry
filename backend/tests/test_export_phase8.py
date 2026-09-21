"""Phase 8 form-style PDF export tests (individual + bulk ``pdf-form``).

Covers the two Phase 8 export surfaces through the public HTTP endpoints:

* ``GET /api/forms/{form_id}/submissions/{submission_id}/export?format=pdf``
  -- formulary-style PDF for ONE record, and
* ``GET /api/forms/{form_id}/submissions/export?format=pdf-form``
  -- bulk formulary-style PDF, exactly one submission per page.

The individual and bulk renderers share one page-layout function, so the
content assertions in ``TestIndividualPdfContent`` apply to both; the bulk
tests focus on page count, query semantics and the record limit while the
individual tests focus on rendering and access rules.

Assertions work on raw PDF properties -- %PDF magic, decompressed content
streams (extractable ASCII), ``/Type /Page`` count, and ToUnicode CMap hex
tokens -- so they stay robust across layout tweaks. Guaranteed behavior:

* authorization (admin / operator / viewer / anonymous / draft / archived)
* ``format`` validation (only ``pdf`` for a single record)
* cross-form isolation on the individual endpoint (404)
* one record per page (page count = record count, empty set = one blank page)
* Phase 5 query semantics on the bulk endpoint (search / filters / sort /
  ignored limit-offset)
* the hard export record limit (no silent truncation)
* per-type rendering (select -> label, radio -> label, checkbox -> Yes/No,
  date / time / datetime, empty values blank, long values capped)
* Unicode: Latin-1 accents render and stay extractable; Devanagari / CJK runs
  are wrapped in registered fonts whose ToUnicode CMaps carry the expected
  code points (skipped when the matching host font is unavailable).
"""

import base64
import json
import re
import zlib
from urllib.parse import urlencode

import pytest

from app.models import Role
from app.services import export_service

from .test_records import (
    _admin,
    _create_form,
    _headers,
    _submit,
)

DEVANAGARI_FONT = export_service._unicode_font("devanagari")
CJK_FONT = export_service._unicode_font("cjk")

SELECT_OPTIONS = [
    {"label": "Engineering", "value": "eng"},
    {"label": "Sales", "value": "sales"},
]
RADIO_OPTIONS = [
    {"label": "Full-time", "value": "full"},
    {"label": "Part-time", "value": "part"},
]

FORM_FIELDS = [
    {"field_key": "full_name", "label": "Full Name", "field_type": "text", "required": True},
    {"field_key": "title", "label": "Job Title", "field_type": "text"},
    {
        "field_key": "department",
        "label": "Department",
        "field_type": "select",
        "required": True,
        "settings": {"options": SELECT_OPTIONS},
    },
    {
        "field_key": "employment",
        "label": "Employment",
        "field_type": "radio",
        "settings": {"options": RADIO_OPTIONS},
    },
    {"field_key": "years", "label": "Years", "field_type": "number"},
    {"field_key": "hired", "label": "Hiring Date", "field_type": "date"},
    {"field_key": "shift", "label": "Shift Start", "field_type": "time"},
    {"field_key": "interview", "label": "Interview Date", "field_type": "datetime"},
    {"field_key": "notes", "label": "Notes", "field_type": "textarea"},
    {"field_key": "agree", "label": "Agreed", "field_type": "checkbox"},
]

RECORD_FULL = {
    "full_name": "Rahul Ahirwar",
    "title": "Lead Engineer",
    "department": "eng",
    "employment": "full",
    "years": 30,
    "hired": "2024-05-12",
    "shift": "09:30",
    "interview": "2025-01-15T10:00:00",
    "notes": "Lead engineer on the platform",
    "agree": True,
}

RECORD_MINIMAL = {
    "full_name": "Priya Sharma",
    "department": "sales",
    "employment": "part",
    "agree": False,
}

RECORD_THIRD = {
    "full_name": "Munyaneza Karangwa",
    "title": None,
    "department": "eng",
    "years": 40,
    "agree": True,
}


def _export(client, headers, form_id, **params):
    query = urlencode(params, doseq=True)
    return client.get(f"/api/forms/{form_id}/submissions/export?{query}", headers=headers)


def _single_export(client, headers, form_id, submission_id, **params):
    query = urlencode(params, doseq=True)
    return client.get(
        f"/api/forms/{form_id}/submissions/{submission_id}/export?{query}",
        headers=headers,
    )


def _seed(client, headers, form_id, records=None):
    ids = []
    for record in (records or [RECORD_FULL, RECORD_MINIMAL, RECORD_THIRD]):
        ids.append(_submit(client, headers, form_id, record))
    return ids


def _pdf_streams(content: bytes) -> list[bytes]:
    """Decompress every content stream in the PDF (an Adobe flat for zlib)."""
    streams: list[bytes] = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", content, re.DOTALL):
        raw = match.group(1).rstrip(b"\r\n")
        decoded = None
        try:
            decoded = base64.a85decode(raw, adobe=True)
        except Exception:
            pass
        for candidate in ([decoded] if decoded else []) + [raw]:
            try:
                streams.append(zlib.decompress(candidate))
                break
            except zlib.error:
                streams.append(candidate)
    return streams


def _pdf_text(content: bytes) -> str:
    """Reconstruct the text a PDF viewer draws.

    reportlab paints non-ASCII (Latin-1/WinAnsi) glyphs inside ``()`` strings
    as octal escapes such as ``\\351`` (é) / ``\\374`` (ü); those escapes are
    resolved back to their WinAnsi bytes so accented text is searchable, while
    pure ASCII runs pass through unchanged.
    """
    joined = b"".join(_pdf_streams(content))

    def resolve(match: re.Match[bytes]) -> bytes:
        return bytes([int(match.group(1), 8)])

    joined = re.sub(rb"\\([0-7]{3})", resolve, joined)
    return joined.decode("latin-1", errors="replace")


def _pdf_page_count(content: bytes) -> int:
    """Count single-page objects (``/Type /Page`` minus the catalog ``/Pages``)."""
    return len(re.findall(rb"/Type\s*/Page(?!s)", content))


def _pdf_hex_tokens(content: bytes) -> set[str]:
    """All 4-hex-ish tokens found in content streams (ToUnicode CMap entries
    appear here because glyph codes and Unicode code points are hex pairs)."""
    tokens: set[str] = set()
    for stream in _pdf_streams(content):
        tokens.update(re.findall(rb"<([0-9a-fA-F]{4})>", stream))
    return {token.decode("ascii").lower() for token in tokens}


def _missing_unicode_tokens(content: bytes, expected: list[str]) -> list[str]:
    tokens = _pdf_hex_tokens(content)
    return [token for token in expected if token not in tokens]


class TestIndividualPdfContent:
    def test_renders_title_labels_and_values(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, name="Employee Onboarding", fields=FORM_FIELDS)
        record_id = _seed(client, admin, form_id, [RECORD_FULL])[0]

        response = _single_export(client, admin, form_id, record_id, format="pdf")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/pdf")
        assert response.content.startswith(b"%PDF")
        text = _pdf_text(response.content)
        assert f"Record #{record_id}" in text
        assert "Employee Onboarding" in text
        assert "Rahul Ahirwar" in text
        assert "Lead Engineer" in text

    def test_all_field_labels_rendered(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        record_id = _seed(client, admin, form_id, [RECORD_FULL])[0]

        text = _pdf_text(_single_export(client, admin, form_id, record_id, format="pdf").content)

        for label in (
            "Full Name",
            "Job Title",
            "Department",
            "Employment",
            "Years",
            "Hiring Date",
            "Shift Start",
            "Interview Date",
            "Notes",
            "Agreed",
        ):
            assert label in text

    def test_select_and_radio_render_labels(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        record_id = _seed(client, admin, form_id, [RECORD_FULL])[0]

        text = _pdf_text(_single_export(client, admin, form_id, record_id, format="pdf").content)

        assert "Engineering" in text  # select value -> label
        assert "Full-time" in text  # radio value -> label

    def test_checkbox_renders_yes_no(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        record_a = _seed(client, admin, form_id, [RECORD_FULL])[0]
        record_b = _seed(client, admin, form_id, [RECORD_MINIMAL])[0]

        text_a = _pdf_text(_single_export(client, admin, form_id, record_a, format="pdf").content)
        text_b = _pdf_text(_single_export(client, admin, form_id, record_b, format="pdf").content)

        assert "Yes" in text_a
        assert "No" in text_b

    def test_temporal_values_rendered_as_text(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        record_id = _seed(client, admin, form_id, [RECORD_FULL])[0]

        text = _pdf_text(_single_export(client, admin, form_id, record_id, format="pdf").content)

        assert "2024-05-12" in text  # date
        assert "09:30" in text  # time
        assert "2025-01-15T10:00:00" in text  # datetime

    def test_empty_fields_render_blank_not_none(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        record_id = _seed(client, admin, form_id, [RECORD_MINIMAL])[0]

        text = _pdf_text(_single_export(client, admin, form_id, record_id, format="pdf").content)

        assert "None" not in text

    def test_long_value_capped_in_pdf(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        record_id = _seed(client, admin, form_id, [{**RECORD_FULL, "notes": "x" * 4000}])[0]

        response = _single_export(client, admin, form_id, record_id, format="pdf")

        assert response.status_code == 200
        assert response.content.startswith(b"%PDF")
        assert _pdf_text(response.content).count("x") <= 400

    def test_latin_extended_text_stays_extractable(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        record_id = _submit(client, admin, form_id, {**RECORD_FULL, "full_name": "Zoé Müller"})

        response = _single_export(client, admin, form_id, record_id, format="pdf")

        assert response.status_code == 200
        text = _pdf_text(response.content)
        assert "Zoé Müller" in text

    def test_content_disposition_and_filename(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, name="Employee Onboarding", fields=FORM_FIELDS)
        record_id = _seed(client, admin, form_id, [RECORD_FULL])[0]

        response = _single_export(client, admin, form_id, record_id, format="pdf")

        disposition = response.headers["content-disposition"]
        assert disposition.startswith("attachment; filename=")
        assert f"employee-onboarding-record-{record_id}.pdf" in disposition


class TestIndividualPdfAccess:
    def test_anonymous_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        record_id = _seed(client, admin, form_id)[0]

        response = _single_export(client, {}, form_id, record_id, format="pdf")

        assert response.status_code == 401

    def test_all_roles_can_export(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        record_id = _seed(client, admin, form_id)[0]
        operator = _headers(client, db_session, "operator", Role.operator)
        viewer = _headers(client, db_session, "viewer", Role.viewer)

        for headers in (admin, operator, viewer):
            response = _single_export(client, headers, form_id, record_id, format="pdf")
            assert response.status_code == 200
            assert response.content.startswith(b"%PDF")

    def test_draft_form_rejected(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS, status="draft")

        response = _single_export(client, admin, form_id, 9999, format="pdf")

        assert response.status_code == 400
        assert "not available for records" in response.json()["detail"]

    def test_archived_form_exportable(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        record_id = _seed(client, admin, form_id)[0]
        result = client.post(f"/api/forms/{form_id}/archive", headers=admin)
        assert result.status_code == 200

        response = _single_export(client, admin, form_id, record_id, format="pdf")

        assert response.status_code == 200
        assert response.content.startswith(b"%PDF")

    def test_nonexistent_form_404(self, client, db_session):
        admin = _admin(client, db_session)

        response = _single_export(client, admin, 99999, 1, format="pdf")

        assert response.status_code == 404

    def test_nonexistent_submission_404(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)

        response = _single_export(client, admin, form_id, 99999, format="pdf")

        assert response.status_code == 404

    def test_cross_form_submission_404(self, client, db_session):
        admin = _admin(client, db_session)
        form_one = _create_form(client, admin, fields=FORM_FIELDS)
        form_two = _create_form(client, admin, name="Second Form", fields=FORM_FIELDS)
        record_id = _seed(client, admin, form_one)[0]

        response = _single_export(client, admin, form_two, record_id, format="pdf")

        assert response.status_code == 404
        assert "Submission not found" in response.json()["detail"]

    def test_unsupported_format_400(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        record_id = _seed(client, admin, form_id)[0]

        response = _single_export(client, admin, form_id, record_id, format="csv")

        assert response.status_code == 400
        assert "can only be exported as 'pdf'" in response.json()["detail"]


class TestBulkFormPdf:
    def test_one_record_per_page(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, name="Employee Onboarding", fields=FORM_FIELDS)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="pdf-form")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/pdf")
        assert response.content.startswith(b"%PDF")
        assert _pdf_page_count(response.content) == 3
        text = _pdf_text(response.content)
        assert "Rahul Ahirwar" in text
        assert "Engineering" in text

    def test_single_record_single_page(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        _seed(client, admin, form_id, [RECORD_FULL])

        response = _export(client, admin, form_id, format="pdf-form")

        assert _pdf_page_count(response.content) == 1

    def test_empty_result_single_blank_page(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)

        response = _export(client, admin, form_id, format="pdf-form")

        assert response.status_code == 200
        assert response.content.startswith(b"%PDF")
        assert _pdf_page_count(response.content) == 1

    def test_search_reduces_pages(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="pdf-form", search="rahul")

        assert response.status_code == 200
        assert _pdf_page_count(response.content) == 1

    def test_filter_reduces_pages(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        _seed(client, admin, form_id)

        filters = json.dumps([{"field": "department", "operator": "equals", "value": "eng"}])
        response = _export(client, admin, form_id, format="pdf-form", filters=filters)

        assert response.status_code == 200
        assert _pdf_page_count(response.content) == 2

    def test_sort_and_ignored_limit_offset(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        _seed(client, admin, form_id)

        response = _export(
            client,
            admin,
            form_id,
            format="pdf-form",
            sort_by="years",
            sort_order="desc",
            limit=1,
            offset=2,
        )

        assert response.status_code == 200
        assert _pdf_page_count(response.content) == 3

    def test_invalid_filter_400(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        _seed(client, admin, form_id)

        response = _export(
            client, admin, form_id, format="pdf-form",
            filters=json.dumps([{"field": "nope", "operator": "equals", "value": 1}]),
        )

        assert response.status_code == 400

    def test_invalid_sort_400(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="pdf-form", sort_order="sideways")

        assert response.status_code == 400

    def test_archived_form_pdf(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        _seed(client, admin, form_id)
        result = client.post(f"/api/forms/{form_id}/archive", headers=admin)
        assert result.status_code == 200

        response = _export(client, admin, form_id, format="pdf-form")

        assert response.status_code == 200
        assert _pdf_page_count(response.content) == 3

    def test_bulk_filename(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, name="Employee Onboarding", fields=FORM_FIELDS)
        _seed(client, admin, form_id)

        response = _export(client, admin, form_id, format="pdf-form")

        disposition = response.headers["content-disposition"]
        assert "employee-onboarding-records-form.pdf" in disposition

    def test_distinct_filename_from_table_pdf(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, name="Employee Onboarding", fields=FORM_FIELDS)
        _seed(client, admin, form_id)

        form_pdf = _export(client, admin, form_id, format="pdf-form")
        table_pdf = _export(client, admin, form_id, format="pdf")

        form_name = "employee-onboarding-records-form.pdf"
        table_name = "employee-onboarding-records.pdf"
        assert form_name in form_pdf.headers["content-disposition"]
        assert table_name in table_pdf.headers["content-disposition"]
        assert form_name != table_name

    def test_over_limit_400_without_truncation(self, client, db_session, monkeypatch):
        monkeypatch.setattr(export_service, "MAX_EXPORT_RECORDS", 2)
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        for index in range(4):
            _submit(client, admin, form_id, {**RECORD_FULL, "title": f"T{index}"})

        response = _export(client, admin, form_id, format="pdf-form")

        assert response.status_code == 400
        assert "Export is limited to 2 records" in response.json()["detail"]

    def test_over_limit_400_for_table_and_csv_too(self, client, db_session, monkeypatch):
        monkeypatch.setattr(export_service, "MAX_EXPORT_RECORDS", 2)
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        for index in range(4):
            _submit(client, admin, form_id, {**RECORD_FULL, "title": f"T{index}"})

        for export_format in ("pdf-form", "pdf", "csv"):
            response = _export(client, admin, form_id, format=export_format)
            assert response.status_code == 400

    @pytest.mark.skipif(not DEVANAGARI_FONT, reason="No Devanagari font registered on this host")
    def test_bulk_with_devangari_ascii_mix(self, client, db_session):
        admin = _admin(client, db_session)
        form_id = _create_form(client, admin, fields=FORM_FIELDS)
        _seed(client, admin, form_id, [{**RECORD_FULL, "full_name": "नमस्ते Rahul"}])

        response = _export(client, admin, form_id, format="pdf-form")

        assert response.status_code == 200
        assert "Rahul" in _pdf_text(response.content)
        assert _missing_unicode_tokens(response.content, ["0928", "092e", "0938"]) == []