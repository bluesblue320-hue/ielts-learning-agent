"""Phase 8 Agent public-route contract tests."""

from fastapi.routing import APIRoute

from app.main import create_app


def test_agent_turn_is_exposed_only_at_the_frozen_writing_path() -> None:
    routes = create_app().openapi()["paths"]
    assert "/learners/{learner_id}/writing/agent/turn" in routes
    assert "/learners/{learner_id}/agent/turn" not in routes