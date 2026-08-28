"""Fail-closed database isolation guard shared by Eval runtime and tests."""

from sqlalchemy.engine import make_url


def validate_test_database_url(
    test_database_url: str,
    development_database_url: str | None = None,
) -> str:
    """Reject a non-test database or a URL shared with development."""

    test_url = make_url(test_database_url)
    database_name = test_url.database or ""
    database_tokens = database_name.lower().replace("-", "_").split("_")
    if "test" not in database_tokens:
        raise ValueError("test database URL must identify an isolated test database")
    if (
        development_database_url is not None
        and make_url(development_database_url) == test_url
    ):
        raise ValueError("test database URL must not match development database URL")
    return test_database_url


__all__ = ["validate_test_database_url"]
