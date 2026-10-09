"""Reset the database to a fresh, production-ready state.

Deletes all sample data (``submissions``, ``form_fields``, ``forms``,
``users``, ``tenants``) and rewinds the primary-key
sequences so new ids start from 1 again. Schema, tables, indexes, and Alembic
migrations are left completely untouched; this script never drops a table.

Usage (from the ``backend`` directory, with the virtual environment active):

    python scripts/reset_database.py                  # confirm, wipe everything
    python scripts/reset_database.py --yes            # wipe without prompting
    python scripts/reset_database.py --dry-run        # preview row counts only

    python scripts/reset_database.py --keep-admin alice --yes
        # Wipe everything EXCEPT one primary super-administrator (their user
        # row and their tenant survive).
        # All forms, fields, submissions, other users, and other tenants are
        # still removed. The kept account must exist and have the admin role.

The database is read from ``backend/.env`` (DATABASE_URL) exactly like the
API, or you can point the script at a different database with
``--database-url <URL>``.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models import Role, User  # noqa: E402

DELETE_ORDER = [
    "submissions",
    "form_fields",
    "forms",
    "users",
    "tenants",
]

SEQUENCE_TABLES = [
    "tenants",
    "users",
    "forms",
    "form_fields",
    "submissions",
]

REQUIRED_TABLES = DELETE_ORDER


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset sample data in the database.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report current row counts and sequences without changing anything.",
    )
    parser.add_argument(
        "--keep-admin",
        metavar="USERNAME",
        help="Keep this single admin account (and its tenant); delete everything else.",
    )
    parser.add_argument(
        "--database-url",
        help="Override the DATABASE_URL from backend/.env for this run.",
    )
    return parser.parse_args()


def _session(database_url: str | None) -> sessionmaker:
    if database_url:
        engine = create_engine(database_url)
        return sessionmaker(bind=engine, autocommit=False, autoflush=False)
    if SessionLocal is None:
        raise RuntimeError(
            "DATABASE_URL is not configured; set it in backend/.env "
            "or pass --database-url."
        )
    return SessionLocal


def _row_count(db: Session, table: str) -> int:
    return int(db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())


def _reset_sequences(db: Session) -> int:
    """Rewind PK sequences so the next id is based on the remaining rows."""
    dialect = db.get_bind().dialect.name
    reset = 0
    for table in SEQUENCE_TABLES:
        max_id = int(
            db.execute(text(f"SELECT COALESCE(MAX(id), 0) FROM {table}")).scalar_one()
        )
        if dialect == "postgresql":
            sequence = db.execute(
                text("SELECT pg_get_serial_sequence(:table, 'id')"),
                {"table": table},
            ).scalar()
            if not sequence:
                continue
            if max_id == 0:
                db.execute(text("SELECT setval(:sequence, 1, false)"), {"sequence": sequence})
            else:
                db.execute(text("SELECT setval(:sequence, :value, true)"), {"sequence": sequence, "value": max_id})
            reset += 1
        elif dialect == "sqlite":
            has_sequence_table = (
                db.execute(
                    text(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'table' AND name = 'sqlite_sequence'"
                    )
                ).scalar()
                is not None
            )
            if has_sequence_table:
                db.execute(
                    text("DELETE FROM sqlite_sequence WHERE name = :table"),
                    {"table": table},
                )
                reset += 1
    return reset


def _resolve_kept_admin(db: Session, keep_admin: str) -> tuple[int, int]:
    """Return (user_id, tenant_id) for the named primary super-admin."""
    kept = db.scalar(select(User).where(User.username == keep_admin))
    if kept is None:
        raise ValueError(f"no user named {keep_admin!r} exists")
    if kept.role is not Role.admin:
        raise ValueError(
            f"{keep_admin!r} has role {kept.role.value!r}; only an admin can be "
            "kept as the primary super-administrator"
        )
    return kept.id, kept.tenant_id


def _clean(
    db: Session, keep_user_id: int | None = None, keep_tenant_id: int | None = None
) -> tuple[dict[str, int], int]:
    counts: dict[str, int] = {}
    for table in DELETE_ORDER:
        counts[table] = _row_count(db, table)
        if keep_user_id is not None:
            if table == "users":
                db.execute(text("DELETE FROM users WHERE id <> :uid"), {"uid": keep_user_id})
                continue
            if table == "tenants":
                db.execute(
                    text("DELETE FROM tenants WHERE id <> :tid"), {"tid": keep_tenant_id}
                )
                continue
        db.execute(text(f"DELETE FROM {table}"))

    reset = _reset_sequences(db)
    db.commit()
    return counts, reset


def _report(args: argparse.Namespace, counts: dict[str, int], reset: int) -> None:
    if args.dry_run:
        print("Dry run — no data was changed.")
        header = "Rows found"
    else:
        header = "Rows deleted"
    print(f"\n{'Table':<14}{header:>14}")
    print("-" * 28)
    for table in DELETE_ORDER:
        print(f"{table:<14}{counts[table]:>14}")
    if args.dry_run:
        return
    if reset:
        print(f"\nReset {reset} primary-key sequence(s).")
    if args.keep_admin:
        print(f"Kept primary administrator {args.keep_admin!r} and their tenant.")
    else:
        print("\nAll users, tenants, forms, and submissions were removed.")


def main() -> int:
    args = _parse_args()
    settings = get_settings()
    factory = _session(args.database_url)

    with factory() as db:
        dialect = db.get_bind().dialect
        missing = [t for t in REQUIRED_TABLES if not dialect.has_table(db.connection(), t)]
        if missing:
            print(
                f"Error: migrations appear not to be applied; missing tables: "
                f"{', '.join(missing)}. Run `alembic upgrade head` first.",
                file=sys.stderr,
            )
            return 1

        keep = args.keep_admin
        keep_user_id: int | None = None
        keep_tenant_id: int | None = None
        if keep is not None:
            try:
                keep_user_id, keep_tenant_id = _resolve_kept_admin(db, keep)
            except ValueError as error:
                print(f"Error: {error}. No changes were made.", file=sys.stderr)
                return 1

        if args.dry_run:
            counts = {t: _row_count(db, t) for t in DELETE_ORDER}
            _report(args, counts, 0)
            return 0

        if not args.yes:
            scope = (
                f"admin account {keep!r} and its tenant"
                if keep is not None
                else "ALL users, tenants, forms, fields, and submissions"
            )
            print(f"This will permanently delete {scope} from the {dialect.name} database.")
            answer = input('Type "reset" to continue: ').strip()
            if answer != "reset":
                print("Aborted. No changes were made.")
                return 1

        counts, reset = _clean(db, keep_user_id, keep_tenant_id)
        _report(args, counts, reset)
        print(f"Environment: {settings.environment}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())