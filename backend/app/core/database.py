"""SQLAlchemy engine, session factory, and declarative base."""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = (
    create_engine(settings.database_url, pool_pre_ping=True)
    if settings.database_url
    else None
)

SessionLocal = (
    sessionmaker(bind=engine, autocommit=False, autoflush=False)
    if engine is not None
    else None
)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session, used as a FastAPI dependency."""
    if SessionLocal is None:
        raise RuntimeError(
            "DATABASE_URL is not configured; set it and restart the API."
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database() -> bool | None:
    """Verify the database is reachable.

    Returns ``True`` when connected, ``False`` on a failed connection, and
    ``None`` when no database is configured.
    """
    if engine is None:
        return None
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False