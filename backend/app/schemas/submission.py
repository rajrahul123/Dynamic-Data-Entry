"""Pydantic schemas for generic form submissions.

Submission payloads are intentionally generic: ``data`` is an opaque JSON
object keyed by the form's field keys. Dynamic validation of that object
happens server-side against the live ``FormField`` definitions before
persistence (see ``app.core.submission_validation``).
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class RecordFilter(BaseModel):
    """One dynamic filter applied to a form's records.

    ``value`` is intentionally untyped: its interpretation (scalar vs. a
    ``[low, high]`` range for ``between``) depends on the referenced field's
    type and is validated by the query service against the live ``FormField``
    definition.
    """

    field: str
    operator: str
    value: Any


class SubmissionCreate(BaseModel):
    data: dict[str, Any] = {}


class SubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    form_id: int
    submitted_by: int
    data: dict[str, Any]
    submitted_at: datetime
    updated_at: datetime


class SubmissionUpdate(BaseModel):
    """Full replacement of an existing submission's ``data`` payload.

    The replacement is validated server-side against the live ``FormField``
    definitions exactly like a fresh submission, so the same field rules a
    phase-3 POST enforces also apply to record edits.
    """

    data: dict[str, Any] = {}


class SubmissionListItem(BaseModel):
    """Row-shaped submission used by the records list/detail endpoints.

    ``submitted_by_user_*`` fields only expose safe identity information
    (username, full name). Password hashes and other sensitive user data are
    never included.
    """

    id: int
    form_id: int
    submitted_by: int
    submitted_by_username: str | None = None
    submitted_by_full_name: str | None = None
    data: dict[str, Any]
    submitted_at: datetime
    updated_at: datetime


class SubmissionDetail(SubmissionListItem):
    """Full record detail; shares the list item shape."""


class SubmissionListResponse(BaseModel):
    items: list[SubmissionListItem]
    total: int
    limit: int
    offset: int