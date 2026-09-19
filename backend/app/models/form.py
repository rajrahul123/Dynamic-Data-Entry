"""Form and form field ORM models.

Forms are generic, data-driven definitions: a ``Form`` owns an ordered list of
``FormField`` rows, each with its own configuration. Nothing here is specific
to any real-world form (student, employee, etc.) — future phases render any
form definition dynamically.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class FormStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class FieldType(str, Enum):
    text = "text"
    textarea = "textarea"
    number = "number"
    email = "email"
    phone = "phone"
    date = "date"
    time = "time"
    datetime = "datetime"
    select = "select"
    radio = "radio"
    checkbox = "checkbox"


class Form(TimestampMixin, Base):
    __tablename__ = "forms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[FormStatus] = mapped_column(
        SAEnum(FormStatus, name="form_status", native_enum=False, length=20),
        nullable=False,
        default=FormStatus.draft,
        server_default=FormStatus.draft.value,
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    fields: Mapped[list["FormField"]] = relationship(
        back_populates="form",
        cascade="all, delete-orphan",
        order_by="FormField.sort_order",
    )
    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="form", passive_deletes=True
    )


class FormField(TimestampMixin, Base):
    __tablename__ = "form_fields"
    __table_args__ = (
        UniqueConstraint(
            "form_id", "field_key", name="uq_form_fields_form_id_field_key"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    form_id: Mapped[int] = mapped_column(
        ForeignKey("forms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    field_type: Mapped[FieldType] = mapped_column(
        SAEnum(FieldType, name="field_type", native_enum=False, length=20),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    placeholder: Mapped[str | None] = mapped_column(String(200), nullable=True)
    required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    settings: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )

    form: Mapped[Form] = relationship(back_populates="fields")