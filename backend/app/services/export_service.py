"""Generic record export service: CSV, Excel (.xlsx), PDF, and SQL.

Everything here is generic and data-driven. Exports are rendered from the
live ``FormField`` definitions (columns follow ``sort_order``, headers use the
field label) plus the ``Submission`` rows themselves — there is no form-
specific knowledge anywhere.

The Phase 5 query engine is reused verbatim: ``build_record_query`` produces
the same WHERE clauses and ORDER BY expressions used by the records list, so a
CSV/Excel/PDF/SQL export honors the exact same ``search`` / ``filters`` /
``sort_by`` / ``sort_order`` semantics as the UI, with no second filtering
implementation. Export never applies ``limit`` / ``offset`` from the Records
page; instead it exports every matching record up to
:data:`MAX_EXPORT_RECORDS`.

Export formats:

* ``csv``  — UTF-8 (with BOM so Excel renders Unicode correctly),
  RFC-4180-style escaping via the standard ``csv`` module.
* ``xlsx`` — single ``Records`` worksheet via ``openpyxl``; native numbers
  and datetime values where practical, header formatting, readable widths.
* ``pdf``  — landscape, wrapped cells, repeated header rows, via reportlab.
* ``sql``  — ``INSERT INTO submissions (...) VALUES (...);`` statements for
  PostgreSQL, safely single-quote-escaped; intended for inspection or data
  migration, **not** a complete database backup.

The SQL export is the *only* format that emits raw ``Submission.data`` JSON;
spreadsheet/PDF exports render only the columns defined by the current form
definition (unknown stored keys are never added as arbitrary columns).
"""

from __future__ import annotations

import csv
import io
import json
import re
import string
from datetime import date, datetime, time
from typing import Any, BinaryIO
from xml.sax.saxutils import escape as xml_escape

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import FieldType, Form, Submission
from app.services.record_query import RecordQueryError, build_record_query

EXPORT_FORMATS = ("csv", "xlsx", "pdf", "sql")

#: Hard server-side cap on exported rows. Exports are synchronous and bounded;
#: a single export larger than this should be narrowed via search/filters.
#: Exceeding the cap is an error (400) -- never a silent truncation.
MAX_EXPORT_RECORDS = 10000

#: Column headers exported before the dynamic form fields (documented).
EXPORT_META_COLUMNS = ("ID", "Submitted By", "Submitted At")

_MEDIA_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "sql": "application/sql",
}

#: Characters stripped from a generated filename; the slug is built only from
#: ASCII letters/digits/dashes so it is always a safe attachment filename.
_FILENAME_PATTERN = re.compile(r"[^a-z0-9]+")


class ExportError(ValueError):
    """Raised for invalid export requests (bad format, oversized dataset)."""


class ExportSizeError(ExportError):
    """Raised when the matching records exceed :data:`MAX_EXPORT_RECORDS`."""


def _option_label(field, value: Any) -> str | None:
    """Resolve a select/radio value (stored value *or* label) to its label."""
    if value is None:
        return None
    raw = str(value)
    for option in (field.settings or {}).get("options") or []:
        if not isinstance(option, dict):
            continue
        if str(option.get("value")) == raw or str(option.get("label")) == raw:
            return str(option.get("label") or option.get("value") or raw)
    return None


def _display_value(field, value: Any) -> str:
    """Human-readable cell value shared by CSV/PDF (Excel builds on this)."""
    if value is None:
        return ""
    if field.field_type in (FieldType.select, FieldType.radio):
        return _option_label(field, value) or str(value)
    if field.field_type is FieldType.checkbox:
        return "Yes" if value is True else "No"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _parse_temporal(field, value: Any) -> date | time | datetime | None:
    """Best-effort parse of stored date/time/datetime text for Excel cells."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    try:
        if field.field_type is FieldType.date:
            return date.fromisoformat(text)
        if field.field_type is FieldType.time:
            return time.fromisoformat(text)
        if field.field_type is FieldType.datetime:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=None)
    except ValueError:
        return None
    return None


def _excel_value(field, value: Any) -> Any:
    """Native value for an Excel cell (numbers/datetimes, else display text)."""
    if value is None:
        return None
    if field.field_type is FieldType.number and isinstance(value, (int, float)) and not isinstance(
        value, bool
    ):
        return value
    if field.field_type in (FieldType.date, FieldType.time, FieldType.datetime):
        parsed = _parse_temporal(field, value)
        if parsed is not None:
            return parsed
    return _display_value(field, value)


def _rows(form: Form, submissions: list[Submission]) -> tuple[list[str], list[list[str]]]:
    """Build the header row and display rows for spreadsheet/PDF exports."""
    fields = sorted(form.fields, key=lambda f: f.sort_order)

    def row_for(submission: Submission) -> list[str]:
        submitter = submission.submitted_by_user
        submitter_name = (
            submitter.full_name
            if submitter and submitter.full_name
            else (submitter.username if submitter else "")
        )
        cells: list[str] = [str(submission.id), submitter_name or "", submission.submitted_at.isoformat() if submission.submitted_at else ""]
        for field in fields:
            cells.append(_display_value(field, submission.data.get(field.field_key)))
        return cells

    headers = [*EXPORT_META_COLUMNS, *[field.label for field in fields]]
    return headers, [row_for(submission) for submission in submissions]


def slugify_filename(form_name: str, form_id: int) -> str:
    """Build a safe, useful filename stem from the form name."""
    slug = _FILENAME_PATTERN.sub("-", form_name.lower()).strip("-").strip(string.punctuation)
    return slug or f"form-{form_id}"


def _fetch_records(
    db: Session,
    form: Form,
    search: str | None,
    filters: str | None,
    sort_by: str | None,
    sort_order: str | None,
) -> list[Submission]:
    """Query matching submissions with the Phase 5 engine (limit enforced)."""
    where, order_by = build_record_query(
        db,
        form,
        search=search,
        filters=filters,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    total_where = and_(*where)
    total = (
        db.scalar(select(func.count()).select_from(Submission).where(total_where)) or 0
    )
    if total > MAX_EXPORT_RECORDS:
        raise ExportSizeError(
            f"Export is limited to {MAX_EXPORT_RECORDS} records. "
            "Narrow the export with search or filters and try again."
        )
    return list(
        db.scalars(
            select(Submission)
            .where(total_where)
            .options(selectinload(Submission.submitted_by_user))
            .order_by(*order_by)
        )
    )


def render_csv(form: Form, submissions: list[Submission]) -> bytes:
    """Render records as UTF-8 CSV (BOM included)."""
    headers, rows = _rows(form, submissions)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


_MULTI_SPACE = re.compile(r"\s+")


def _column_width(label: str) -> int:
    text = _MULTI_SPACE.sub(" ", label.strip())
    return min(max(len(text), 12), 40)


def render_xlsx(form: Form, submissions: list[Submission]) -> bytes:
    """Render records as a single ``Records`` worksheet (.xlsx)."""
    headers, _rows_display = _rows(form, submissions)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Records"
    worksheet.freeze_panes = "A2"

    for index, header in enumerate(headers, start=1):
        cell = worksheet.cell(row=1, column=index, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        cell.alignment = Alignment(vertical="center")
        worksheet.column_dimensions[cell.column_letter].width = _column_width(header)

    fields = _ordered_fields(form)
    first_data_column = len(EXPORT_META_COLUMNS) + 1

    for row_index, submission in enumerate(submissions, start=2):
        worksheet.cell(row=row_index, column=1, value=submission.id)
        submitter = submission.submitted_by_user
        submitter_name = (
            submitter.full_name
            if submitter and submitter.full_name
            else (submitter.username if submitter else "")
        )
        worksheet.cell(row=row_index, column=2, value=submitter_name or None)
        worksheet.cell(
            row=row_index,
            column=3,
            value=submission.submitted_at.replace(tzinfo=None) if submission.submitted_at else None,
        )
        for offset, field in enumerate(fields):
            column = first_data_column + offset
            worksheet.cell(
                row=row_index,
                column=column,
                value=_excel_value(field, submission.data.get(field.field_key)),
            )

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _ordered_fields(form: Form):
    return sorted(form.fields, key=lambda f: f.sort_order)


def render_pdf(form: Form, submissions: list[Submission]) -> bytes:
    """Render records as a landscape PDF table with repeated headers.

    Long text is wrapped per cell (CJK, so any character can break). Single
    cells longer than :data:`_PDF_RECORD_CELL_LIMIT` characters are truncated
    with ``...``: an unbroken 10k-character blob in one narrow cell would
    otherwise grow a table row taller than the page and reportlab would abort
    the whole export with a LayoutError. CSV / XLSX / SQL always carry the
    complete value; the cap exists only so the PDF renderer is always safe.
    """
    headers, rows = _rows(form, submissions)

    buffer: BinaryIO = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=0.4 * inch,
        leftMargin=0.4 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        title=f"Records — {form.name}",
        author="Dynamic Data Entry Platform",
    )
    available_width = landscape(letter)[0] - 0.8 * inch

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ExportTitle",
        parent=styles["Title"],
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
    )
    meta_style = ParagraphStyle(
        "ExportMeta",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.grey,
    )
    cell_style = ParagraphStyle(
        "ExportCell",
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
        wordWrap="CJK",
    )
    header_style = ParagraphStyle(
        "ExportHeaderCell",
        parent=styles["Normal"],
        fontSize=7.5,
        leading=9,
        textColor=colors.white,
        fontName="Helvetica-Bold",
    )

    story = [Paragraph(f"Records — {xml_escape(form.name)}", title_style)]
    exported_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    story.append(
        Paragraph(
            xml_escape(
                f"Form ID {form.id} · exported {exported_at} · "
                f"{len(submissions)} record(s)"
            ),
            meta_style,
        )
    )
    story.append(Spacer(1, 0.15 * inch))

    column_count = len(headers)
    column_width = available_width / max(column_count, 1)

    table_data: list[list[Paragraph]] = []
    table_data.append([Paragraph(xml_escape(header), header_style) for header in headers])
    for row in rows:
        table_data.append([Paragraph(xml_escape(_pdf_cell_text(cell)), cell_style) for cell in row])

    table = Table(
        table_data,
        colWidths=[column_width] * column_count,
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return buffer.getvalue()


_PDF_RECORD_CELL_LIMIT = 400


def _pdf_cell_text(value: str, limit: int = _PDF_RECORD_CELL_LIMIT) -> str:
    """Truncate extremely long cells so a table row can always paginate.

    PDF cells wrap (CJK) normally; only a pathological single value would ever
    exceed the cap. CSV / XLSX / SQL carry the complete value -- this exists
    purely so the PDF renderer can never abort with a reportlab LayoutError.
    """
    if len(value) > limit:
        return value[: limit - 3].rstrip() + "..."
    return value


def _sql_quote(value: str) -> str:
    """Single-quote a PostgreSQL string literal (safe against ``'``)."""
    return "'" + value.replace("'", "''") + "'"


def render_sql(form: Form, submissions: list[Submission]) -> bytes:
    """Render records as portable PostgreSQL INSERT statements.

    The output targets the real ``submissions`` table schema. It represents
    submission data for inspection / migration and is deliberately *not* a
    complete database backup (users, forms, fields, configuration, and other
    tables are not included).
    """
    exported_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "-- Dynamic Data Entry Platform record export",
        f"-- Form: {form.name} (#{form.id})",
        f"-- Exported: {exported_at}",
        f"-- Records: {len(submissions)}",
        "-- Purpose: inspection / migration of submission data. This is NOT a",
        "-- complete database backup: other tables (users, forms, ...) are omitted.",
        "-- No user credentials, password hashes, or secrets are exported.",
        "SET standard_conforming_strings = on;",
        "BEGIN;",
        "INSERT INTO submissions (form_id, submitted_by, data, submitted_at)",
        "VALUES",
    ]
    parts: list[str] = []
    for index, submission in enumerate(submissions):
        data = json.dumps(submission.data, ensure_ascii=False, separators=(",", ":"))
        submitted_at = (
            submission.submitted_at.isoformat()
            if submission.submitted_at
            else datetime.now().isoformat()
        )
        values = (
            f"  ({int(submission.form_id)}, {int(submission.submitted_by)}, "
            f"{_sql_quote(data)}::jsonb, "
            f"{_sql_quote(submitted_at)})"
        )
        separator = ";" if index == len(submissions) - 1 else ","
        parts.append(values + separator)
    lines.extend(parts)
    lines.append("COMMIT;")
    return "\n".join(lines).encode("utf-8")


def generate_export(
    db: Session,
    form: Form,
    *,
    format: str,
    search: str | None,
    filters: str | None,
    sort_by: str | None,
    sort_order: str | None,
) -> tuple[bytes, str, str]:
    """Generate an export and return ``(content, media_type, extension)``.

    ``format`` is validated here (400-style error for anything outside
    ``EXPORT_FORMATS``). Search / filter / sort parameters are delegated to
    the Phase 5 query engine and may raise :class:`RecordQueryError`.
    """
    if format not in EXPORT_FORMATS:
        raise ExportError(
            f"Unsupported export format: {format}. "
            f"Supported formats: {', '.join(EXPORT_FORMATS)}"
        )

    submissions = _fetch_records(db, form, search, filters, sort_by, sort_order)

    if format == "csv":
        return render_csv(form, submissions), _MEDIA_TYPES["csv"], "csv"
    if format == "xlsx":
        return render_xlsx(form, submissions), _MEDIA_TYPES["xlsx"], "xlsx"
    if format == "pdf":
        return render_pdf(form, submissions), _MEDIA_TYPES["pdf"], "pdf"
    return render_sql(form, submissions), _MEDIA_TYPES["sql"], "sql"