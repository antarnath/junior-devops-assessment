"""Shared pytest fixtures.

The tests run against an in-memory SQLite database so they are fast and need
no other services running.
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Must be set before app.main is imported so the engine points at SQLite.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")

from app.main import Base, app, get_db  # noqa: E402


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """A session bound to a fresh in-memory database."""
    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)

    TestingSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


@pytest.fixture
def client(db_session) -> Generator[TestClient, None, None]:
    """A test client wired to the in-memory database."""
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_operation() -> dict[str, object]:
    """A valid operation payload."""
    return {
        "reference": "OPS-1001",
        "title": "Warehouse stock reconciliation",
        "priority": 2,
        "notes": "Synthetic test data.",
    }
