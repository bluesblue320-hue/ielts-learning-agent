"""Lazy Agent tool factories that preserve FastAPI dependency overrides."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Request

from app.api.dependencies.practice import get_practice_generator
from app.api.dependencies.writing import get_writing_provider


def get_agent_generator_factory(request: Request) -> Callable[[], object]:
    """Return, but do not invoke, the configured practice generator factory."""

    return request.app.dependency_overrides.get(
        get_practice_generator,
        get_practice_generator,
    )


def get_agent_provider_factory(request: Request) -> Callable[[], object]:
    """Return, but do not invoke, the configured writing provider factory."""

    return request.app.dependency_overrides.get(
        get_writing_provider,
        get_writing_provider,
    )