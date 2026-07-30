from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


engine: Engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.

    A new SQLAlchemy session is created for each request and is always closed
    afterwards, regardless of whether the request succeeds or raises an
    exception.
    """
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()