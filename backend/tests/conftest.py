"""Test fixtures.

Environment variables are set *before* importing the application so that
settings resolve to a test database and test secret instead of the local
``.env`` values. Tests use an in-memory SQLite database and override the
FastAPI ``get_db`` dependency.
"""

import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"

from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.database import get_db  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Role, User  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """Give every test a clean per-IP window for the auth rate limiter."""
    limiter.reset()


def _make_engine():
    return create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture()
def db_engine():
    engine = _make_engine()
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Generator[Session, None, None]:
    testing_session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = testing_session()
    yield session
    session.close()


@pytest.fixture()
def client(db_engine) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        testing_session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_user(
    db_session: Session,
    username: str,
    email: str,
    password: str = "password123",
    role: Role = Role.viewer,
    is_active: bool = True,
) -> User:
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        full_name=f"{username} full name",
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def login_headers(client: TestClient, username: str, password: str = "password123") -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}