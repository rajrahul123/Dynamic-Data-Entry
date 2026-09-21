"""Generic form submission & record-management endpoints.

Submission endpoints accept any authenticated, active user. Their job is to
expose published (and, for record management, archived) form definitions for
rendering and to accept validated submissions.

Record-management endpoints (list / detail / update / delete) serve the same
generic ``Submission.data`` JSON regardless of the real-world form: there are
no form-specific tables or columns. All authorization decisions use the
existing role infrastructure:

* list / detail — any authenticated role (admin, operator, viewer)
* create (new submissions) — admin or operator (viewer -> 403, anonymous -> 401)
* update / delete — admin or operator (viewer -> 403, anonymous -> 401)

Validation is fully dynamic: payloads are checked against the live
``FormField`` definitions via ``app.core.submission_validation`` and only
persisted after every rule passes. Updating an existing record reuses the
exact same engine used for new submissions, so edit behavior and submission
behavior can never diverge.
"""

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import (
    ActiveSubscription,
    CurrentOperator,
    CurrentUser,
    DbSession,
)
from app.core.submission_validation import validate_submission_data
from app.models import Form, FormStatus, Submission
from app.schemas import (
    FormRead,
    SubmissionCreate,
    SubmissionDetail,
    SubmissionListResponse,
    SubmissionRead,
    SubmissionUpdate,
)
from app.services import export_service
from app.services.record_query import RecordQueryError, build_record_query

router = APIRouter(prefix="/forms", tags=["submissions"])


def _load_form(db: Session, form_id: int, *, load_fields: bool = False) -> Form:
    statement = select(Form).where(Form.id == form_id)
    if load_fields:
        statement = statement.options(selectinload(Form.fields))
    form = db.scalar(statement)
    if form is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Form not found"
        )
    return form


def _require_accepting_submissions(form: Form) -> None:
    if form.status is not FormStatus.published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This form is not open for submissions",
        )


def _require_record_visibility(form: Form) -> None:
    if form.status not in (FormStatus.published, FormStatus.archived):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This form is not available for records",
        )


def _load_submission(db: Session, form_id: int, submission_id: int) -> Submission:
    """Load a submission that provably belongs to the requested form.

    If the submission id exists under a different form it is treated exactly
    like a missing id (404) so cross-form data is never exposed.
    """
    submission = db.scalar(
        select(Submission)
        .where(Submission.id == submission_id, Submission.form_id == form_id)
        .options(selectinload(Submission.submitted_by_user))
    )
    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found"
        )
    return submission


def _serialize(submission: Submission) -> dict:
    """Build a safe record response from an ORM submission.

    Only the submitter's username / full name are included; password hashes
    and other sensitive user columns are never serialized.
    """
    submitter = submission.submitted_by_user
    return {
        "id": submission.id,
        "form_id": submission.form_id,
        "submitted_by": submission.submitted_by,
        "submitted_by_username": submitter.username if submitter else None,
        "submitted_by_full_name": submitter.full_name if submitter else None,
        "data": submission.data,
        "submitted_at": submission.submitted_at,
        "updated_at": submission.updated_at,
    }


@router.get("/{form_id}/definition", response_model=FormRead)
def get_form_definition(form_id: int, db: DbSession, user: CurrentUser) -> Form:
    """Fetch a form definition for rendering.

    Published forms are rendered for both submission and record management.
    Archived forms are also exposed so their **historical** records remain
    viewable/editable; draft definitions stay hidden.
    """
    form = _load_form(db, form_id, load_fields=True)
    _require_record_visibility(form)
    return form


@router.post(
    "/{form_id}/submissions",
    response_model=SubmissionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_submission(
    form_id: int,
    payload: SubmissionCreate,
    db: DbSession,
    user: CurrentOperator,
    _subscription: ActiveSubscription,
) -> Submission:
    """Accept a new submission for a published form (admin/operator).

    Submission is a write operation, so it is restricted to staff roles:
    viewers are rejected with 403 and anonymous requests with 401. This stops
    a viewer role from injecting data even though they can read definitions
    and records.
    """
    form = _load_form(db, form_id, load_fields=True)
    _require_accepting_submissions(form)

    errors = validate_submission_data(form.fields, payload.data)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=errors
        )

    submission = Submission(
        form_id=form.id,
        tenant_id=form.tenant_id,
        submitted_by=user.id,
        data=payload.data,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


@router.get("/{form_id}/submissions", response_model=SubmissionListResponse)
def list_submissions(
    form_id: int,
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    filters: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_order: str | None = Query(default=None),
) -> dict:
    """Paginated list of a form's records (any authenticated role).

    Supports server-side free-text search, dynamic per-type filters, and
    sorting -- all driven by the form's live ``FormField`` definitions:

    * ``search``   plain-text substring across text-like fields.
    * ``filters``  URL-encoded JSON array, e.g.
      ``filters=[{"field":"age","operator":"greater_than","value":18},
      {"field":"name","operator":"contains","value":"rah"}]``; multiple
      filters are AND-combined.
    * ``sort_by``  a form field key; ``sort_order`` ``asc``/``desc``.
      Without ``sort_by``, records come back newest-first (Phase 4 default).
    """
    form = _load_form(db, form_id, load_fields=True)
    _require_record_visibility(form)

    try:
        where, order_by = build_record_query(
            db,
            form,
            search=search,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except RecordQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    total_where = and_(*where)
    total = (
        db.scalar(
            select(func.count())
            .select_from(Submission)
            .where(total_where)
        )
        or 0
    )

    items = [
        _serialize(submission)
        for submission in db.scalars(
            select(Submission)
            .where(total_where)
            .options(selectinload(Submission.submitted_by_user))
            .order_by(*order_by)
            .limit(limit)
            .offset(offset)
        )
    ]

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{form_id}/submissions/export")
def export_submissions(
    form_id: int,
    db: DbSession,
    user: CurrentUser,
    _subscription: ActiveSubscription,
    format: str = Query(...),
    search: str | None = Query(default=None),
    filters: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_order: str | None = Query(default=None),
) -> Response:
    """Export a form's records as CSV / XLSX / PDF / SQL / form-style PDF
    (any authenticated role).

    Export is a read operation, so the same access rules as the records list
    apply: admin / operator / viewer may export; anonymous requests are
    rejected (401); draft forms are not available for exports; published and
    archived forms are. The Phase 5 query engine is reused verbatim, so
    ``search`` / ``filters`` / ``sort_by`` / ``sort_order`` behave exactly as
    on the records page. ``limit`` / ``offset`` are never applied -- every
    matching record is exported up to the configured safety limit.

    ``format``:

    * ``csv`` / ``xlsx`` / ``sql`` -- table exports (Phase 6).
    * ``pdf`` -- landscape table PDF (Phase 6).
    * ``pdf-form`` -- portrait form-style PDF, one record per page (Phase 8).
    """
    form = _load_form(db, form_id, load_fields=True)
    _require_record_visibility(form)

    try:
        content, media_type, _extension = export_service.generate_export(
            db,
            form,
            format=format,
            search=search,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except (RecordQueryError, export_service.ExportError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    filename = export_service.export_filename(form, format)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{form_id}/submissions/{submission_id}/export")
def export_single_submission(
    form_id: int,
    submission_id: int,
    db: DbSession,
    user: CurrentUser,
    _subscription: ActiveSubscription,
    format: str = Query(...),
) -> Response:
    """Export ONE record as a form-style PDF (any authenticated role).

    Reuses the record-detail access rules: the submission must belong to the
    requested form (cross-form ids -> 404), the form must be published or
    archived (draft -> 400), and anonymous requests are rejected (401). Only
    ``format=pdf`` is meaningful here; anything else -> 400.
    """
    form = _load_form(db, form_id, load_fields=True)
    _require_record_visibility(form)

    if format != "pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported export format: {format}. "
                "A single record can only be exported as 'pdf'."
            ),
        )

    submission = _load_submission(db, form_id, submission_id)
    filename = export_service.individual_pdf_filename(form, submission.id)
    return Response(
        content=export_service.render_form_pdf(form, submission),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{form_id}/submissions/{submission_id}", response_model=SubmissionDetail
)
def get_submission(
    form_id: int,
    submission_id: int,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    """Return one record (any authenticated role)."""
    form = _load_form(db, form_id)
    _require_record_visibility(form)
    return _serialize(_load_submission(db, form_id, submission_id))


@router.patch(
    "/{form_id}/submissions/{submission_id}", response_model=SubmissionDetail
)
def update_submission(
    form_id: int,
    submission_id: int,
    payload: SubmissionUpdate,
    db: DbSession,
    user: CurrentOperator,
    _subscription: ActiveSubscription,
) -> dict:
    """Edit an existing record (admin/operator; viewer -> 403).

    The lifecycle restriction is intentionally *not* re-used here: archived
    forms block new submissions but their historical records must stay
    editable/deletable. The data payload is validated with the same dynamic
    engine as new submissions.
    """
    form = _load_form(db, form_id, load_fields=True)
    _require_record_visibility(form)
    submission = _load_submission(db, form_id, submission_id)

    errors = validate_submission_data(form.fields, payload.data)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=errors
        )

    submission.data = payload.data
    db.commit()
    db.refresh(submission)
    return _serialize(submission)


@router.delete(
    "/{form_id}/submissions/{submission_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_submission(
    form_id: int,
    submission_id: int,
    db: DbSession,
    user: CurrentOperator,
    _subscription: ActiveSubscription,
) -> None:
    """Delete a single record (admin/operator; viewer -> 403).

    This is a record-level operation: the form, its fields, and every other
    submission are untouched.
    """
    form = _load_form(db, form_id)
    _require_record_visibility(form)
    submission = _load_submission(db, form_id, submission_id)
    db.delete(submission)
    db.commit()