"""
Shared pytest fixtures for Billson's Tasks.

Database-backed tests use a dedicated PostgreSQL test database. Each test is
wrapped in an outer transaction that is rolled back afterwards, including when
application services call Session.commit().
"""

from collections.abc import Generator
from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.core.config import settings
from app.db.base import Base


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_ENV_FILE = PROJECT_ROOT / ".env.test"


def load_test_database_url() -> str:
    """
    Load and validate TEST_DATABASE_URL from .env.test.

    The safety checks deliberately reject the normal application database and
    any database whose name does not end in "_test".
    """
    if not TEST_ENV_FILE.is_file():
        raise RuntimeError(
            "The test environment file was not found at "
            f"'{TEST_ENV_FILE}'. Create .env.test before running "
            "database-backed tests.",
        )

    test_environment = dotenv_values(
        TEST_ENV_FILE,
    )

    raw_database_url = test_environment.get(
        "TEST_DATABASE_URL",
    )

    if raw_database_url is None:
        raise RuntimeError(
            "TEST_DATABASE_URL is missing from .env.test.",
        )

    test_database_url = raw_database_url.strip()

    if not test_database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL cannot be empty.",
        )

    parsed_test_url = make_url(
        test_database_url,
    )
    parsed_application_url = make_url(
        settings.database_url,
    )

    test_database_name = parsed_test_url.database

    if not test_database_name:
        raise RuntimeError(
            "TEST_DATABASE_URL must include a database name.",
        )

    if not test_database_name.casefold().endswith(
        "_test",
    ):
        raise RuntimeError(
            "Refusing to run database-backed tests because the database "
            f"'{test_database_name}' does not end in '_test'.",
        )

    if parsed_test_url.render_as_string(
        hide_password=False,
    ) == parsed_application_url.render_as_string(
        hide_password=False,
    ):
        raise RuntimeError(
            "Refusing to run because TEST_DATABASE_URL points to the "
            "application database.",
        )

    return test_database_url


TEST_DATABASE_URL = load_test_database_url()


@pytest.fixture(
    scope="session",
)
def test_engine() -> Generator[Engine, None, None]:
    """
    Create the test database engine and schema for the pytest session.
    """
    engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
        future=True,
    )

    Base.metadata.create_all(
        bind=engine,
    )

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db(
    test_engine: Engine,
) -> Generator[Session, None, None]:
    """
    Provide an isolated SQLAlchemy session for one test.

    An outer connection transaction is rolled back after the test. Nested
    savepoints allow application code to call db.commit() without committing
    changes permanently to the test database.
    """
    connection: Connection = test_engine.connect()
    outer_transaction = connection.begin()

    TestSessionLocal = sessionmaker(
        bind=connection,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    session = TestSessionLocal()
    session.begin_nested()

    @event.listens_for(
        session,
        "after_transaction_end",
    )
    def restart_savepoint(
        session: Session,
        transaction: object,
    ) -> None:
        nested = getattr(
            transaction,
            "nested",
            False,
        )
        parent = getattr(
            transaction,
            "_parent",
            None,
        )
        parent_is_nested = getattr(
            parent,
            "nested",
            False,
        )

        if nested and not parent_is_nested:
            session.expire_all()
            session.begin_nested()

    try:
        yield session
    finally:
        event.remove(
            session,
            "after_transaction_end",
            restart_savepoint,
        )

        session.close()

        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()