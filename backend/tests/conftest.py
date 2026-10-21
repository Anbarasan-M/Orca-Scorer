"""Pytest configuration and transactional fixtures.

Mirrors Laravel's `DatabaseTransactions` / `RefreshDatabase` trait:
opens a transaction before each test, binds the session to a savepoint,
and rolls everything back after the test finishes so tests never leak data.
"""

import os
import sys

# Ensure backend root is on Python module path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import engine, get_db
from app.main import app


@pytest.fixture(scope="session")
def db_engine():
    """Shared database engine for the test run."""
    return engine


@pytest.fixture
def db_session(db_engine):
    """Transactional database fixture.

    Uses a nested SAVEPOINT so that if route code calls `db.commit()`,
    only the savepoint commits. The outer transaction is always rolled back
    when the test exits, keeping the database perfectly pristine.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session):
    """FastAPI TestClient with `get_db` dependency overridden to use the transactional session."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
