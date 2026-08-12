"""SQLAlchemy engine and session lifecycle."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def create_db_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy 2.x engine without opening a connection eagerly."""
    return create_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create the application's configured session factory."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@lru_cache
def get_engine() -> Engine:
    """Create and cache the process-wide application engine."""
    settings = get_settings()
    return create_db_engine(settings.database_url.get_secret_value())


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Create and cache the process-wide application session factory."""
    return create_session_factory(get_engine())


def get_db_session() -> Generator[Session, None, None]:
    """Yield one database session and always close it after use."""
    factory = get_session_factory()
    with factory() as session:
        yield session
