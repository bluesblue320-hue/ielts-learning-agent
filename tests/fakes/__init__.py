"""Deterministic test doubles unavailable to application runtime."""

from tests.fakes.llm import FakeProvider
from tests.fakes.practice_generator import FakePracticeGenerator

__all__ = ["FakePracticeGenerator", "FakeProvider"]
