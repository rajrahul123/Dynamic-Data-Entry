"""Dynamic server-side validation of submission payloads.

Validation is driven *entirely* by the database ``FormField`` definitions:
field type, ``required`` flag, and per-type ``settings``. There is no
hard-coded knowledge of any specific real-world form (employee, student,
etc.), so the same rules apply to any form created through the builder.

Every rule mirrors the Phase 2 builder constraints (the same settings the
builder validated at definition time are enforced here at submission time).
The frontend validation is a UX convenience only — this module is the
security boundary.
"""

from datetime import date, datetime, time
from email_validator import EmailNotValidError, validate_email
import re

from app.core.payload_limits import MAX_UNCONFIGURED_STRING_LENGTH
from app.models import FieldType, FormField

_MISSING = object()

PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9 ()+-]{5,19}$")


def _error_detail(loc: tuple[str | int, ...], message: str) -> dict:
    return {
        "loc": list(loc),
        "msg": message,
        "type": "value_error",
    }


def _to_number(value: object) -> int | float | None:
    """Coerce a submitted number (numeric or numeric string) to a value."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        try:
            return float(text) if any(c in text for c in ".eE") else int(text)
        except ValueError:
            return None
    return None


def _is_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _validate_text_like(field: FormField, value: object) -> str | None:
    if not isinstance(value, str):
        return "Must be a string"
    settings = field.settings or {}
    min_length = settings.get("min_length")
    max_length = settings.get("max_length")
    if min_length is not None and len(value) < int(min_length):
        return f"Must be at least {min_length} characters"
    if max_length is not None and len(value) > int(max_length):
        return f"Must be at most {max_length} characters"
    if max_length is None and len(value) > MAX_UNCONFIGURED_STRING_LENGTH:
        return f"Must be at most {MAX_UNCONFIGURED_STRING_LENGTH} characters"
    return None


def _validate_number(field: FormField, value: object) -> str | None:
    number = _to_number(value)
    if number is None:
        return "Must be a valid number"
    settings = field.settings or {}
    minimum = settings.get("min")
    maximum = settings.get("max")
    step = settings.get("step")
    if minimum is not None and number < float(minimum):
        return f"Must be at least {minimum}"
    if maximum is not None and number > float(maximum):
        return f"Must be at most {maximum}"
    if step is not None:
        base = float(minimum) if minimum is not None else 0.0
        step_value = float(step)
        if step_value > 0:
            diff = number - base
            if abs(diff) > 1e-9:
                quotient = diff / step_value
                if abs(quotient - round(quotient)) > 1e-6:
                    return f"Must be a multiple of {step}"
    return None


def _validate_email(value: object) -> str | None:
    if not isinstance(value, str):
        return "Must be a string"
    try:
        validate_email(value.strip(), check_deliverability=False)
    except EmailNotValidError:
        return "Must be a valid email address"
    return None


def _validate_phone(value: object) -> str | None:
    if not isinstance(value, str):
        return "Must be a string"
    if not PHONE_PATTERN.fullmatch(value.strip()):
        return "Must be a valid phone number"
    return None


def _validate_date(value: object) -> str | None:
    if not isinstance(value, str):
        return "Must be a string"
    try:
        date.fromisoformat(value.strip())
    except ValueError:
        return "Must be a valid date (YYYY-MM-DD)"
    return None


def _validate_time(value: object) -> str | None:
    if not isinstance(value, str):
        return "Must be a string"
    try:
        time.fromisoformat(value.strip())
    except ValueError:
        return "Must be a valid time (HH:MM or HH:MM:SS)"
    return None


def _validate_datetime(value: object) -> str | None:
    if not isinstance(value, str):
        return "Must be a string"
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return "Must be a valid ISO date-time (e.g. 2026-09-19T10:30:00)"
    return None


def _validate_choice(field: FormField, value: object) -> str | None:
    if not isinstance(value, str):
        return "Must be a string"
    options = (field.settings or {}).get("options") or []
    valid_values = {o.get("value") for o in options if isinstance(o, dict)}
    valid_labels = {o.get("label") for o in options if isinstance(o, dict)}
    if value not in valid_values and value not in valid_labels:
        return "Not a valid option"
    return None


def _validate_value(field: FormField, value: object) -> str | None:
    field_type = field.field_type
    if field_type in (FieldType.text, FieldType.textarea):
        return _validate_text_like(field, value)
    if field_type is FieldType.number:
        return _validate_number(field, value)
    if field_type is FieldType.email:
        return _validate_email(value)
    if field_type is FieldType.phone:
        return _validate_phone(value)
    if field_type is FieldType.date:
        return _validate_date(value)
    if field_type is FieldType.time:
        return _validate_time(value)
    if field_type is FieldType.datetime:
        return _validate_datetime(value)
    if field_type in (FieldType.select, FieldType.radio):
        return _validate_choice(field, value)
    if field_type is FieldType.checkbox:
        if not isinstance(value, bool):
            return "Must be true or false"
        return None
    return f"Unsupported field type: {field_type}"


def validate_submission_data(
    fields: list[FormField], data: dict
) -> list[dict]:
    """Validate a submission payload against form field definitions.

    Returns a list of FastAPI-style error detail dicts. Each has
    ``loc``/``msg``/``type`` keys; empty means the payload is valid.
    """
    errors: list[dict] = []
    defined_keys = {field.field_key for field in fields}

    # Reject unknown keys instead of silently discarding them.
    for key in data:
        if key not in defined_keys:
            errors.append(_error_detail(("body", "data", key), "Unknown field"))

    for field in sorted(fields, key=lambda f: f.sort_order):
        key = field.field_key
        value = data.get(key, _MISSING)
        loc = ("body", "data", key)

        if field.field_type is FieldType.checkbox:
            if field.required:
                if not isinstance(value, bool) or value is not True:
                    errors.append(
                        _error_detail(loc, "This checkbox must be checked")
                    )
            elif value is not _MISSING and not isinstance(value, bool):
                errors.append(_error_detail(loc, "Must be true or false"))
            continue

        if field.required and (value is _MISSING or _is_empty(value)):
            errors.append(_error_detail(loc, "This field is required"))
            continue

        if value is _MISSING or value is None:
            continue

        message = _validate_value(field, value)
        if message is not None:
            errors.append(_error_detail(loc, message))

    return errors