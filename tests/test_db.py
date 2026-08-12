"""Tests for SQLAlchemy foundation infrastructure."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase

from app.db.base import Base
from app.db.session import create_db_engine, create_session_factory


def test_base_uses_sqlalchemy_two_declarative_api() -> None:
    assert issubclass(Base, DeclarativeBase)


@pytest.mark.integration
def test_engine_and_session_execute_against_postgresql(database_url: str) -> None:
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)

    try:
        with factory() as session:
            assert session.scalar(text("SELECT 1")) == 1
    finally:
        engine.dispose()


def test_database_connection_failures_are_explicit() -> None:
    engine = create_db_engine(
        "postgresql+psycopg://user:password@127.0.0.1:1/unavailable"
        "?connect_timeout=1"
    )

    try:
        with pytest.raises(OperationalError):
            with engine.connect():
                pass
    finally:
        engine.dispose()
