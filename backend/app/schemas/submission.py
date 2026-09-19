"""Pydantic schemas for generic form submissions.

Submission payloads are intentionally generic: ``data`` is an opaque JSON
object keyed by the form's field keys. Dynamic validation of that object
happens server-side against the live ``FormField`` definitions before
persistence (see ``app.core.submission_validation``).
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


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