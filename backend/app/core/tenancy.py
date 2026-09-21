"""Implicit multi-tenant data isolation.

Every business model carries a ``tenant_id`` column. Rather than remember to
add a ``WHERE tenant_id = ...`` at each call site, this module hooks
:class:`sqlalchemy.orm.Session` and rewrites *every* ORM SELECT so that
tenant-scoped entities are automatically filtered to the session's tenant.

A tenant context is attached to the session object itself (``session.info
["tenant_id"]``) by ``app.api.deps.get_current_user`` as soon as an
authenticated user is resolved. That has two important consequences:

* The user lookup inside ``get_current_user`` runs *before* the context is
  set, so login/me can find a user regardless of tenant.
* Every later query -- including lazy loads and ``selectinload`` subqueries
  fired during response serialization -- is scoped to the user's tenant,
  regardless of which thread FastAPI's dependency runs on.

Public endpoints (registration, forgot/reset password, login) never set a
tenant context, so their cross-tenant lookups continue to work normally.
"""

from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from app.models import Form, FormField, Submission, User

TENANT_SCOPED_MODELS = (User, Form, FormField, Submission)

TENANT_CONTEXT_KEY = "tenant_id"


def current_tenant_id(db: Session) -> int | None:
    """Return the active tenant id bound to a session, if any."""
    return db.info.get(TENANT_CONTEXT_KEY)


def bind_tenant(db: Session, tenant_id: int) -> None:
    """Bind a session to a tenant; all subsequent ORM queries are scoped."""
    db.info[TENANT_CONTEXT_KEY] = tenant_id


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_scope(state) -> None:
    """Rewrite ORM SELECTs to add tenant predicates for scoped models.

    Uses ``with_loader_criteria`` so the predicate also covers lazy loads and
    ``selectinload`` / ``joinedload`` loader statements (``include_aliases``
    keeps the predicate correct inside aliased SQL). The statement is
    untouched when no tenant is bound.
    """
    if not state.is_select:
        return

    tenant_id = state.session.info.get(TENANT_CONTEXT_KEY)
    if tenant_id is None:
        return

    statement = state.statement
    for model in TENANT_SCOPED_MODELS:
        statement = statement.options(
            with_loader_criteria(
                model,
                model.tenant_id == tenant_id,
                include_aliases=True,
            )
        )
    state.statement = statement