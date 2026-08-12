"""Deterministic health-check services."""

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


def database_is_available(session: Session) -> bool:
    """Return database availability without exposing connection details."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True
