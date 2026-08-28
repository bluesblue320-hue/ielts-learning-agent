"""Compatibility import for the shared Eval/test database isolation guard."""

from app.eval.isolation import validate_test_database_url


__all__ = ["validate_test_database_url"]
