"""Generic form submission endpoints.

Unlike the admin-only forms builder router, these endpoints accept any
authenticated, active user. Their job is to expose *published* form
definitions for rendering and to accept validated submissions.

Validation is fully dynamic: the payload is checked against the live
``FormField`` definitions via ``app.core.submission_validation`` and only
persisted after every rule passes.
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.submission_validation import validate_submission_data
from app.models import Form, FormStatus, Submission
from app.schemas import FormRead, SubmissionCreate, SubmissionRead

router = APIRouter(prefix="/forms", tags=["submissions"])


def _load_form_with_fields(db: Session, form_id: int) -> Form:
    form = db.scalar(
        select(Form)
        .where(Form.id == form_id)
        .options(selectinload(Form.fields))
    )
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


@router.get("/{form_id}/definition", response_model=FormRead)
def get_published_form(form_id: int, db: DbSession, user: CurrentUser) -> Form:
    """Fetch a published form's definition for rendering.

    Draft and archived forms are never exposed here; only published forms
    can receive submissions.
    """
    form = _load_form_with_fields(db, form_id)
    _require_accepting_submissions(form)
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
    user: CurrentUser,
) -> Submission:
    form = _load_form_with_fields(db, form_id)
    _require_accepting_submissions(form)

    errors = validate_submission_data(form.fields, payload.data)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=errors
        )

    submission = Submission(
        form_id=form.id,
        submitted_by=user.id,
        data=payload.data,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission