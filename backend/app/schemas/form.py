"""Pydantic schemas for dynamic forms and form fields.

Field settings are validated per field type. Only fields appropriate to a
type are accepted, so malformed or unsafe configuration is rejected before it
is stored.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import FieldType, FormStatus

FIELD_KEY_PATTERN = r"^[a-z][a-z0-9_]*$"
MAX_OPTIONS = 100

# Field types that behave like simple text inputs.
TEXT_LIKE_TYPES = frozenset(
    {
        FieldType.text,
        FieldType.textarea,
        FieldType.email,
        FieldType.phone,
        FieldType.date,
        FieldType.time,
        FieldType.datetime,
    }
)


class SelectOption(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9_-]+$")


class FieldSettings(BaseModel):
    """Type-specific settings stored in the ``settings`` JSON column."""

    min_length: int | None = Field(default=None, ge=0, le=1_000_000)
    max_length: int | None = Field(default=None, ge=0, le=1_000_000)
    min: float | None = None
    max: float | None = None
    step: float | None = Field(default=None, gt=0)
    options: list[SelectOption] | None = Field(default=None, max_length=MAX_OPTIONS)
    checkbox_label: str | None = Field(default=None, max_length=200)


class FieldSettingsError(ValueError):
    """Raised when settings are invalid for the given field type."""


def validate_settings(field_type: FieldType, settings: FieldSettings) -> dict:
    """Validate and normalize settings for a field type.

    Returns the settings dict to store (``None`` values removed). Raises
    ``FieldSettingsError`` for unsupported or malformed configuration.
    """
    data = settings.model_dump(exclude_none=True)

    if field_type in (FieldType.select, FieldType.radio):
        options = data.get("options")
        if not options:
            raise FieldSettingsError(
                f"options are required for {field_type.value} fields"
            )
        values = [option["value"] for option in options]
        if len(values) != len(set(values)):
            raise FieldSettingsError("option values must be unique")
        extra = set(data.keys()) - {"options"}
        if extra:
            raise FieldSettingsError(
                f"options is the only setting allowed for {field_type.value} fields"
            )
        return data

    if field_type is FieldType.checkbox:
        if "options" in data:
            raise FieldSettingsError("options are not allowed for checkbox fields")
        extra = set(data.keys()) - {"checkbox_label"}
        if extra:
            raise FieldSettingsError(
                "checkbox_label is the only setting allowed for checkbox fields"
            )
        return data

    if field_type is FieldType.number:
        if "options" in data:
            raise FieldSettingsError("options are not allowed for number fields")
        if data.get("min") is not None and data.get("max") is not None:
            if data["min"] > data["max"]:
                raise FieldSettingsError("min must not be greater than max")
        return data

    if field_type in TEXT_LIKE_TYPES:
        if "options" in data:
            raise FieldSettingsError(
                f"options are not allowed for {field_type.value} fields"
            )
        extra = set(data.keys()) - {"min_length", "max_length"}
        if extra:
            raise FieldSettingsError(
                f"only min_length/max_length are allowed for {field_type.value} fields"
            )
        if (
            data.get("min_length") is not None
            and data.get("max_length") is not None
            and data["min_length"] > data["max_length"]
        ):
            raise FieldSettingsError("min_length must not be greater than max_length")
        return data

    raise FieldSettingsError(f"unknown field type {field_type!r}")


class FieldCreate(BaseModel):
    field_key: str = Field(min_length=1, max_length=100, pattern=FIELD_KEY_PATTERN)
    label: str = Field(min_length=1, max_length=200)
    field_type: FieldType
    description: str | None = Field(default=None, max_length=1000)
    placeholder: str | None = Field(default=None, max_length=200)
    required: bool = False
    default_value: str | None = Field(default=None, max_length=1000)
    sort_order: int | None = Field(default=None, ge=0, le=1_000_000)
    settings: FieldSettings | None = None


class FieldUpdate(BaseModel):
    field_key: str | None = Field(default=None, min_length=1, max_length=100, pattern=FIELD_KEY_PATTERN)
    label: str | None = Field(default=None, min_length=1, max_length=200)
    field_type: FieldType | None = None
    description: str | None = Field(default=None, max_length=1000)
    placeholder: str | None = Field(default=None, max_length=200)
    required: bool | None = None
    default_value: str | None = Field(default=None, max_length=1000)
    sort_order: int | None = Field(default=None, ge=0, le=1_000_000)
    settings: FieldSettings | None = None


class FieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    form_id: int
    field_key: str
    label: str
    field_type: FieldType
    description: str | None
    placeholder: str | None
    required: bool
    default_value: str | None
    sort_order: int
    settings: dict | None
    created_at: datetime
    updated_at: datetime


class FieldReorder(BaseModel):
    """Ordered list of the form's field ids (must match exactly)."""

    field_ids: list[int] = Field(min_length=0, max_length=500)


class FormCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class FormUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class FormRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    status: FormStatus
    created_by: int
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    fields: list[FieldRead] = []


class AvailableFormRead(BaseModel):
    """Read-only form summary for record browsing by non-admin roles.

    Deliberately minimal: only the identity and lifecycle status needed to
    list a form as a record source. Builder details stay admin-only.
    """

    id: int
    name: str
    description: str | None = None
    status: FormStatus
    updated_at: datetime