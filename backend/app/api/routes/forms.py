"""Admin-only dynamic form builder endpoints.

Forms and their fields are fully generic; nothing here references a specific
real-world form. All mutations are restricted to draft forms so published
definitions cannot be silently changed (full versioning arrives in a later
phase).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import CurrentAdmin, DbSession, require_admin
from app.models import FieldType, Form, FormField, FormStatus
from app.schemas import (
    FieldCreate,
    FieldRead,
    FieldReorder,
    FieldSettings,
    FieldUpdate,
    FormCreate,
    FormRead,
    FormUpdate,
)
from app.schemas.form import FieldSettingsError, validate_settings

router = APIRouter(
    prefix="/forms",
    tags=["forms"],
    dependencies=[Depends(require_admin)],
)


def _not_found(message: str = "Form not found") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)


def _conflict(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def _get_form(db: Session, form_id: int, *, load_fields: bool = True) -> Form:
    statement = select(Form).where(Form.id == form_id)
    if load_fields:
        statement = statement.options(selectinload(Form.fields))
    form = db.scalar(statement)
    if form is None:
        raise _not_found()
    return form


def _require_draft(form: Form) -> None:
    if form.status is not FormStatus.draft:
        raise _conflict("Only draft forms can be modified")


def _get_field(db: Session, form_id: int, field_id: int) -> FormField:
    field = db.scalar(
        select(FormField).where(
            FormField.id == field_id, FormField.form_id == form_id
        )
    )
    if field is None:
        raise _not_found("Field not found in this form")
    return field


def _next_sort_order(db: Session, form_id: int) -> int:
    max_order = db.scalar(
        select(func.coalesce(func.max(FormField.sort_order), -1)).where(
            FormField.form_id == form_id
        )
    )
    return int(max_order) + 1


def _ensure_key_unique(
    db: Session, form_id: int, field_key: str, exclude_id: int | None
) -> None:
    existing = db.scalar(
        select(FormField).where(
            FormField.form_id == form_id, FormField.field_key == field_key
        )
    )
    if existing is not None and existing.id != exclude_id:
        raise _conflict("A field with this key already exists in the form")


def _resolve_settings(field_type: FieldType, settings: FieldSettings | None) -> dict:
    try:
        return validate_settings(field_type, settings or FieldSettings())
    except FieldSettingsError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )


# --------------------------------------------------------------------------- #
# Forms
# --------------------------------------------------------------------------- #


@router.post("", response_model=FormRead, status_code=status.HTTP_201_CREATED)
def create_form(payload: FormCreate, db: DbSession, admin: CurrentAdmin) -> Form:
    form = Form(
        name=payload.name,
        description=payload.description,
        status=FormStatus.draft,
        created_by=admin.id,
    )
    db.add(form)
    db.commit()
    db.refresh(form)
    return form


@router.get("", response_model=list[FormRead])
def list_forms(
    db: DbSession,
    form_status: FormStatus | None = Query(default=None, alias="status"),
    created_by: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Form]:
    statement = select(Form).options(selectinload(Form.fields))
    if form_status is not None:
        statement = statement.where(Form.status == form_status)
    if created_by is not None:
        statement = statement.where(Form.created_by == created_by)
    statement = statement.order_by(Form.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(statement))


@router.get("/{form_id}", response_model=FormRead)
def get_form(form_id: int, db: DbSession) -> Form:
    return _get_form(db, form_id)


@router.patch("/{form_id}", response_model=FormRead)
def update_form(
    form_id: int, payload: FormUpdate, db: DbSession, admin: CurrentAdmin
) -> Form:
    form = _get_form(db, form_id)
    _require_draft(form)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(form, field, value)
    db.commit()
    db.refresh(form)
    return form


@router.delete("/{form_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_form(form_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    form = _get_form(db, form_id)
    _require_draft(form)
    db.delete(form)
    db.commit()


@router.post("/{form_id}/publish", response_model=FormRead)
def publish_form(form_id: int, db: DbSession, admin: CurrentAdmin) -> Form:
    form = _get_form(db, form_id)
    if form.status is not FormStatus.draft:
        raise _conflict("Only draft forms can be published")
    if not form.fields:
        raise _bad_request("A form must have at least one field before publishing")
    form.status = FormStatus.published
    form.published_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(form)
    return form


@router.post("/{form_id}/archive", response_model=FormRead)
def archive_form(form_id: int, db: DbSession, admin: CurrentAdmin) -> Form:
    form = _get_form(db, form_id)
    if form.status is FormStatus.archived:
        raise _conflict("Form is already archived")
    form.status = FormStatus.archived
    db.commit()
    db.refresh(form)
    return form


# --------------------------------------------------------------------------- #
# Form fields
# --------------------------------------------------------------------------- #


@router.post("/{form_id}/fields", response_model=FieldRead, status_code=status.HTTP_201_CREATED)
def create_field(
    form_id: int, payload: FieldCreate, db: DbSession, admin: CurrentAdmin
) -> FormField:
    form = _get_form(db, form_id)
    _require_draft(form)
    _ensure_key_unique(db, form_id, payload.field_key, None)
    settings = _resolve_settings(payload.field_type, payload.settings)

    field = FormField(
        form_id=form_id,
        field_key=payload.field_key,
        label=payload.label,
        field_type=payload.field_type,
        description=payload.description,
        placeholder=payload.placeholder,
        required=payload.required,
        default_value=payload.default_value,
        sort_order=(
            payload.sort_order
            if payload.sort_order is not None
            else _next_sort_order(db, form_id)
        ),
        settings=settings or None,
    )
    db.add(field)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict("A field with this key already exists in the form")
    db.refresh(field)
    return field


@router.patch("/{form_id}/fields/{field_id}", response_model=FieldRead)
def update_field(
    form_id: int,
    field_id: int,
    payload: FieldUpdate,
    db: DbSession,
    admin: CurrentAdmin,
) -> FormField:
    form = _get_form(db, form_id)
    _require_draft(form)
    field = _get_field(db, form_id, field_id)

    changes = payload.model_dump(exclude_unset=True)

    if "field_key" in changes:
        _ensure_key_unique(db, form_id, changes["field_key"], field_id)

    effective_type = changes.get("field_type", field.field_type)
    if "settings" in changes:
        settings_value = _resolve_settings(effective_type, payload.settings)
    elif "field_type" in changes:
        existing = (
            FieldSettings(**field.settings) if field.settings else FieldSettings()
        )
        settings_value = _resolve_settings(effective_type, existing)
    else:
        settings_value = field.settings

    changes["field_type"] = effective_type
    changes["settings"] = settings_value or None

    for name, value in changes.items():
        setattr(field, name, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict("A field with this key already exists in the form")
    db.refresh(field)
    return field


@router.delete("/{form_id}/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_field(form_id: int, field_id: int, db: DbSession, admin: CurrentAdmin) -> None:
    form = _get_form(db, form_id)
    _require_draft(form)
    field = _get_field(db, form_id, field_id)
    db.delete(field)
    db.commit()


@router.post("/{form_id}/fields/reorder", response_model=list[FieldRead])
def reorder_fields(
    form_id: int, payload: FieldReorder, db: DbSession, admin: CurrentAdmin
) -> list[FormField]:
    form = _get_form(db, form_id)
    _require_draft(form)

    ids = payload.field_ids
    if len(ids) != len(set(ids)):
        raise _bad_request("field_ids must not contain duplicates")

    existing = db.scalars(
        select(FormField).where(FormField.form_id == form_id)
    ).all()
    existing_ids = {field.id for field in existing}
    if set(ids) != existing_ids:
        raise _bad_request(
            "field_ids must contain exactly the field ids of this form"
        )

    id_to_field = {field.id: field for field in existing}
    for index, field_id in enumerate(ids):
        id_to_field[field_id].sort_order = index

    # Atomically persist all order changes in one transaction.
    db.commit()

    ordered = db.scalars(
        select(FormField)
        .where(FormField.form_id == form_id)
        .order_by(FormField.sort_order)
    ).all()
    return list(ordered)