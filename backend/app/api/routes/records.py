"""Read-only form listing that powers the records browser.

The Phase 2 ``GET /api/forms`` endpoint is admin-only because it exposes the
builder surface. Operators and viewers need a read-only list of forms that
can have records (published or archived) so the frontend can offer a
record-management entry point without exposing the builder.
"""

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import Form, FormStatus
from app.schemas import AvailableFormRead

router = APIRouter(prefix="/records", tags=["records"])


@router.get("/forms", response_model=list[AvailableFormRead])
def list_record_forms(db: DbSession, user: CurrentUser) -> list[Form]:
    """List forms whose records can be managed (any authenticated role).

    Only published and archived forms appear; drafts are never exposed here.
    """
    statement = (
        select(Form)
        .where(Form.status.in_([FormStatus.published, FormStatus.archived]))
        .order_by(Form.updated_at.desc())
    )
    return list(db.scalars(statement))