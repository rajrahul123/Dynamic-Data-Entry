"""Generic submission ORM model.

A ``Submission`` stores the answers to a *published* ``Form`` as a single JSON
payload keyed by the form's ``FormField.field_key`` values. There are no
form-specific tables (employee_submissions, student_submissions, etc.): any
form created through the builder uses this same row shape.

The submitted data is treated strictly as an opaque JSON document at the
database layer; the dynamic validation of that document happens in
``app.core.submission_validation`` before the row is persisted.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Submission(TimestampMixin, Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    form_id: Mapped[int] = mapped_column(
        ForeignKey("forms.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    submitted_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    data: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
        server_default="{}",
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    form: Mapped["Form"] = relationship(back_populates="submissions", passive_deletes=True)
    submitted_by_user: Mapped["User"] = relationship(
        back_populates="submissions", passive_deletes=True
    )