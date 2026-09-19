"""Dynamic search, filter, and sort building for generic Submission records.

Everything here is generic and data-driven: expressions are built from the
live ``FormField`` definitions (``field_key`` / ``field_type`` / ``settings``)
and applied against the ``Submission.data`` JSON payload. There is no form-
specific knowledge, no string-built SQL, and no ``eval`` — values are always
bound parameters.

Cross-dialect JSON extraction (tests run on in-memory SQLite; production uses
PostgreSQL JSONB):

* PostgreSQL: ``data ->> 'key'`` (unquoted text)
* SQLite:    ``json_extract(data, '$.key')`` (unquoted value)

Temporal values (date / time / datetime) are compared as normalized,
chronologically sortable text (fixed-width, zero-padded ISO parts) so the same
SQL works on both backends.

Invalid filter / sort requests raise :class:`RecordQueryError`; the API layer
converts that into a ``400 Bad Request`` response.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time
from typing import Any

from pydantic import ValidationError
from sqlalchemy import Boolean, Float, Text, and_, cast, func, or_
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models import FieldType, FormField, Submission
from app.schemas import RecordFilter

TEXT_LIKE_OPERATORS = ("equals", "contains", "starts_with", "ends_with")
NUMBER_OPERATORS = (
    "equals",
    "not_equals",
    "greater_than",
    "greater_than_or_equal",
    "less_than",
    "less_than_or_equal",
    "between",
)
DATE_OPERATORS = ("equals", "before", "after", "on_or_before", "on_or_after", "between")
TIME_OPERATORS = ("equals", "before", "after", "between")
DATETIME_OPERATORS = (
    "equals",
    "before",
    "after",
    "on_or_before",
    "on_or_after",
    "between",
)
SELECT_OPERATORS = ("equals", "not_equals")
CHECKBOX_OPERATORS = ("equals",)

FIELD_OPERATORS: dict[FieldType, tuple[str, ...]] = {
    FieldType.text: TEXT_LIKE_OPERATORS,
    FieldType.textarea: TEXT_LIKE_OPERATORS,
    FieldType.email: TEXT_LIKE_OPERATORS,
    FieldType.phone: TEXT_LIKE_OPERATORS,
    FieldType.number: NUMBER_OPERATORS,
    FieldType.date: DATE_OPERATORS,
    FieldType.time: TIME_OPERATORS,
    FieldType.datetime: DATETIME_OPERATORS,
    FieldType.select: SELECT_OPERATORS,
    FieldType.radio: SELECT_OPERATORS,
    FieldType.checkbox: CHECKBOX_OPERATORS,
}

SEARCHABLE_TYPES = frozenset(
    {
        FieldType.text,
        FieldType.textarea,
        FieldType.email,
        FieldType.phone,
        FieldType.select,
        FieldType.radio,
    }
)


class RecordQueryError(ValueError):
    """Raised for malformed or invalid search / filter / sort requests."""


def _is_postgresql(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def _raw_value(db: Session, key: str) -> ColumnElement:
    """SQL expression yielding the field's stored JSON value."""
    if _is_postgresql(db):
        return Submission.data.op("->>")(key)
    return func.json_extract(Submission.data, "$." + key)


def _value_text(db: Session, key: str) -> ColumnElement:
    """Field value as text (safe for equality / wildcard search)."""
    return cast(_raw_value(db, key), Text)


def _value_number(db: Session, key: str) -> ColumnElement:
    """Field value as a float (handles numeric JSON and numeric strings)."""
    return cast(_raw_value(db, key), Float)


def _value_boolean(db: Session, key: str) -> ColumnElement:
    """Field value as a boolean expression.

    On PostgreSQL the ``->>`` text ('true' / 'false') is cast to boolean; on
    SQLite ``json_extract`` already returns 1/0 for JSON booleans, which the
    CAST-to-BOOLEAN then normalizes identically.
    """
    return cast(_raw_value(db, key), Boolean)


def _field_by_key(fields: list[FormField]) -> dict[str, FormField]:
    return {field.field_key: field for field in fields}


def _ensure_field(fields_by_key: dict[str, FormField], key: str) -> FormField:
    field = fields_by_key.get(key)
    if field is None:
        raise RecordQueryError(f"Unknown filter or sort field: {key}")
    return field


def _ensure_operator(field: FormField, operator: str) -> None:
    allowed = FIELD_OPERATORS.get(field.field_type, ())
    if operator not in allowed:
        raise RecordQueryError(
            f"Operator '{operator}' is not supported for field "
            f"'{field.field_key}' of type '{field.field_type.value}'"
        )


def _as_number(value: Any, label: str) -> int | float:
    try:
        if isinstance(value, bool):
            raise ValueError
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                raise ValueError
            return float(text) if any(c in text for c in ".eE") else int(text)
        raise ValueError
    except ValueError:
        raise RecordQueryError(f"{label} must be a number") from None


def _as_boolean(value: Any, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise RecordQueryError(f"{label} must be a boolean")


def _as_text(value: Any, label: str) -> str:
    if isinstance(value, bool) or isinstance(value, (int, float)) or isinstance(value, str):
        return str(value)
    raise RecordQueryError(f"{label} must be a string")


def _as_date(value: Any, label: str) -> str:
    text = _as_text(value, label)
    try:
        return date.fromisoformat(text.strip()).isoformat()
    except ValueError:
        raise RecordQueryError(f"{label} must be a valid date (YYYY-MM-DD)") from None


def _as_time(value: Any, label: str) -> str:
    text = _as_text(value, label)
    try:
        return time.fromisoformat(text.strip()).strftime("%H:%M")
    except ValueError:
        raise RecordQueryError(f"{label} must be a valid time (HH:MM)") from None


def _as_datetime(value: Any, label: str) -> str:
    text = _as_text(value, label)
    try:
        parsed = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        raise RecordQueryError(
            f"{label} must be a valid date-time (e.g. 2026-09-19T10:30:00)"
        ) from None


def _as_range(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list) or len(value) != 2:
        raise RecordQueryError(f"{label} must be an array [low, high]")
    return value


def _temporal_column(db: Session, key: str, field_type: FieldType) -> ColumnElement:
    text_expression = _value_text(db, key)
    if field_type is FieldType.date:
        return func.substr(text_expression, 1, 10)
    if field_type is FieldType.time:
        return func.substr(text_expression, 1, 5)
    return func.substr(func.replace(text_expression, "T", " "), 1, 16)


def _choice_accepted_values(field: FormField, value: Any) -> set[str]:
    option_text = _as_text(value, f"Option for field '{field.field_key}'")
    options = (field.settings or {}).get("options") or []
    accepted: set[str] = set()
    for option in options or []:
        if not isinstance(option, dict):
            continue
        if option.get("value") == option_text or option.get("label") == option_text:
            if option.get("value"):
                accepted.add(str(option["value"]))
            if option.get("label"):
                accepted.add(str(option["label"]))
    if not accepted:
        raise RecordQueryError(
            f"'{option_text}' is not a valid option for field '{field.field_key}'"
        )
    return accepted


def _comparison_clause(
    column: ColumnElement, operator: str, value: Any
) -> ColumnElement:
    comparisons = {
        "equals": _eq,
        "not_equals": _neq,
        "greater_than": lambda col, v: col > v,
        "greater_than_or_equal": lambda col, v: col >= v,
        "less_than": lambda col, v: col < v,
        "less_than_or_equal": lambda col, v: col <= v,
        "before": lambda col, v: col < v,
        "after": lambda col, v: col > v,
        "on_or_before": lambda col, v: col <= v,
        "on_or_after": lambda col, v: col >= v,
    }
    if operator == "between":
        low, high = value
        return and_(column >= low, column <= high)
    if operator not in comparisons:
        raise RecordQueryError(f"Unsupported operator: {operator}")
    return comparisons[operator](column, value)


def _eq(column: ColumnElement, value: Any) -> ColumnElement:
    return column == value


def _neq(column: ColumnElement, value: Any) -> ColumnElement:
    return or_(column.is_(None), column != value)


def parse_filters(raw: str | None) -> list[RecordFilter]:
    """Decode the ``filters`` query parameter into validated filter objects."""
    if raw is None or not raw.strip():
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RecordQueryError(f"Invalid filters JSON: {exc.msg}") from exc
    if not isinstance(payload, list):
        raise RecordQueryError("Filters must be a JSON array")
    filters: list[RecordFilter] = []
    for item in payload:
        try:
            record_filter = RecordFilter.model_validate(item)
        except ValidationError as exc:
            first = exc.errors()[0]
            raise RecordQueryError(
                f"Invalid filter: {first['msg']} at {first['loc']}"
            ) from exc
        filters.append(record_filter)
    return filters


def build_filter_clauses(
    db: Session, fields: list[FormField], filters: list[RecordFilter]
) -> list[ColumnElement]:
    """Build one WHERE clause per filter (all are AND-combined by the caller)."""
    fields_by_key = _field_by_key(fields)
    clauses: list[ColumnElement] = []
    for record_filter in filters:
        clause = _build_filter(db, _ensure_field(fields_by_key, record_filter.field), record_filter)
        clauses.append(clause)
    return clauses


def _build_filter(
    db: Session, field: FormField, record_filter: RecordFilter
) -> ColumnElement:
    _ensure_operator(field, record_filter.operator)
    key = field.field_key
    operator = record_filter.operator
    value = record_filter.value
    field_type = field.field_type

    if field_type in (FieldType.text, FieldType.textarea, FieldType.email, FieldType.phone):
        text = _as_text(value, f"Value for field '{key}'")
        column = _value_text(db, key)
        lowered = func.lower(column)
        lowered_value = text.lower()
        if operator == "equals":
            return lowered == lowered_value
        if operator == "contains":
            return lowered.contains(lowered_value, autoescape=True)
        if operator == "starts_with":
            return lowered.startswith(lowered_value, autoescape=True)
        if operator == "ends_with":
            return lowered.endswith(lowered_value, autoescape=True)
        raise RecordQueryError(f"Unsupported operator for text field '{key}'")

    if field_type is FieldType.number:
        column = _value_number(db, key)
        if operator == "between":
            lo, hi = [_as_number(v, f"Value for field '{key}'") for v in _as_range(value, f"Value for field '{key}'")]
            return and_(column >= lo, column <= hi)
        number = _as_number(value, f"Value for field '{key}'")
        return _comparison_clause(column, operator, number)

    if field_type in (FieldType.date, FieldType.time, FieldType.datetime):
        if operator == "between":
            bound = _as_range(value, f"Value for field '{key}'")
            column = _temporal_column(db, key, field_type)
            if field_type is FieldType.date:
                low, high = [_as_date(v, f"Value for field '{key}'") for v in bound]
            elif field_type is FieldType.time:
                low, high = [_as_time(v, f"Value for field '{key}'") for v in bound]
            else:
                low, high = [_as_datetime(v, f"Value for field '{key}'") for v in bound]
            return and_(column >= low, column <= high)
        column = _temporal_column(db, key, field_type)
        if field_type is FieldType.date:
            bound = _as_date(value, f"Value for field '{key}'")
        elif field_type is FieldType.time:
            bound = _as_time(value, f"Value for field '{key}'")
        else:
            bound = _as_datetime(value, f"Value for field '{key}'")
        return _comparison_clause(column, operator, bound)

    if field_type in (FieldType.select, FieldType.radio):
        accepted = _choice_accepted_values(field, value)
        column = _value_text(db, key)
        if operator == "equals":
            return column.in_(list(accepted))
        return or_(column.is_(None), column.notin_(list(accepted)))

    if field_type is FieldType.checkbox:
        boolean_value = _as_boolean(value, f"Value for field '{key}'")
        return _value_boolean(db, key) == boolean_value

    raise RecordQueryError(f"Unsupported field type: {field_type.value}")


def build_search_clause(
    db: Session, fields: list[FormField], search: str | None
) -> ColumnElement | None:
    """Case-insensitive substring search across human-readable fields."""
    if search is None or not search.strip():
        return None
    term = search.strip().lower()
    searchable = [field for field in fields if field.field_type in SEARCHABLE_TYPES]
    if not searchable:
        return None
    clauses = [
        func.lower(_value_text(db, field.field_key)).contains(term, autoescape=True)
        for field in searchable
    ]
    return or_(*clauses)


def build_order_by(
    db: Session,
    fields: list[FormField],
    sort_by: str | None,
    sort_order: str | None,
) -> list[ColumnElement]:
    """Build ORDER BY expressions.

    * No ``sort_by``      -> ``submitted_at DESC, id DESC`` (Phase 4 default).
    * ``sort_by`` given   -> sort expression + ``submitted_at DESC, id DESC``
      tie-breakers so pagination stays deterministic.

    ``sort_order`` must be ``asc`` or ``desc``; anything else is rejected.
    """
    order = sort_order.lower() if sort_order else "desc"
    if order not in ("asc", "desc"):
        raise RecordQueryError("sort_order must be 'asc' or 'desc'")
    direction = _ascending if order == "asc" else _descending

    if sort_by is None or not sort_by.strip():
        return [Submission.submitted_at.desc(), Submission.id.desc()]

    fields_by_key = _field_by_key(fields)
    field = _ensure_field(fields_by_key, sort_by)
    key = field.field_key
    field_type = field.field_type

    if field_type is FieldType.number:
        expression: ColumnElement = _value_number(db, key)
    elif field_type in (FieldType.date, FieldType.time, FieldType.datetime):
        expression = _temporal_column(db, key, field_type)
    else:
        expression = _value_text(db, key)

    return [
        direction(expression).nullslast(),
        Submission.submitted_at.desc(),
        Submission.id.desc(),
    ]


def _ascending(column: ColumnElement) -> Any:
    return column.asc()


def _descending(column: ColumnElement) -> Any:
    return column.desc()