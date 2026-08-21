from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.learning_application import LearnerNotFoundError
from app.services.writing_guidance import WritingGuidanceService


class _Rows:
    def __init__(self, rows): self._rows = rows
    def all(self): return self._rows


class _Session:
    def __init__(self, learner, states=(), update=None, recommendation=None):
        self.learner = learner; self.states = states; self.update = update; self.recommendation = recommendation
        self.scalar_calls = 0; self.rollback_calls = 0
    def get(self, _model, _identifier): return self.learner
    def scalars(self, _query): return _Rows(self.states)
    def scalar(self, _query):
        self.scalar_calls += 1
        return self.update if self.scalar_calls == 1 else self.recommendation
    def rollback(self): self.rollback_calls += 1


def _learner():
    return SimpleNamespace(id=1, writing_target_band=Decimal("7.0"), created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_no_accepted_update_returns_safe_empty_provider_free_response() -> None:
    response = WritingGuidanceService(_Session(_learner())).get(learner_id=1)
    assert response.current_recommendation is None
    assert response.guidance_items == ()
    assert response.source_citations == ()


def test_practice_recommendation_uses_grounded_citations() -> None:
    state = SimpleNamespace(skill="task_response", estimated_band=Decimal("6.25"))
    update = SimpleNamespace(id=9)
    recommendation = SimpleNamespace(
        id=10, decision_type="practice", target_skill="task_response",
        learner_target_band=Decimal("7.0"), current_estimate=Decimal("6.25"),
        reason_codes=["largest_target_gap"],
    )
    response = WritingGuidanceService(_Session(_learner(), (state,), update, recommendation)).get(learner_id=1)
    assert response.current_recommendation is not None
    assert response.guidance_items[0].criterion == "task_response"
    assert response.guidance_items[0].citations == response.source_citations
    assert all(citation.source_id.startswith("ielts-") for citation in response.source_citations)


def test_no_practice_does_not_invent_a_training_target() -> None:
    response = WritingGuidanceService(_Session(
        _learner(), update=SimpleNamespace(id=9),
        recommendation=SimpleNamespace(id=10, decision_type="no_practice", target_skill=None, learner_target_band=Decimal("7.0"), current_estimate=None, reason_codes=["target_achieved"]),
    )).get(learner_id=1)
    assert response.guidance_items == ()
    assert response.current_recommendation.target_skill is None


def test_unknown_learner_is_not_found() -> None:
    with pytest.raises(LearnerNotFoundError):
        WritingGuidanceService(_Session(None)).get(learner_id=1)
