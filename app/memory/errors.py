"""Shared Phase 6 memory read-model errors."""

from __future__ import annotations


class MemoryReadError(Exception):
    """Base error for Phase 6 memory read-model services."""


class EpisodeNotFoundError(MemoryReadError):
    """The requested learner-owned L0 episode does not exist."""


class MemoryPersistenceError(MemoryReadError):
    """An unexpected SQLAlchemy/PostgreSQL failure during a memory read.

    The API maps this to a safe generic 503; it never exposes raw SQL,
    constraint names, database URLs, exception text, or source contents.
    """


class MemoryInvariantError(MemoryReadError):
    """Persisted rows violate a frozen memory invariant.

    Raised only for defensive consistency checks (e.g., an unreachable resume
    branch). The API maps it to a safe generic failure.
    """
