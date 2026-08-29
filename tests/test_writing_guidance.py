from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.learning_application import LearnerNotFoundError, LearningPersistenceError
from app.services.writing_guidance import WritingGuidanceService, _wiki_page_links


class _Session:
    def __init__(self, learner, update=None, recommendation=None):
        self.learner = learner
        self.update = update
        self.recommendation = recommendation
        self.scalar_calls = 0
        self.rollback_calls = 0

    def get(self, _model, _identifier):
        return self.learner

    def scalar(self, _query):
        self.scalar_calls += 1
        return self.update if self.scalar_calls == 1 else self.recommendation

    def rollback(self):
        self.rollback_calls += 1


def _learner():
    return SimpleNamespace(
        id=1,
        writing_target_band=Decimal("7.0"),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _snapshot(*, task_response: str, other: str) -> dict[str, object]:
    updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {
        skill: {
            "learner_id": 1,
            "skill": skill,
            "estimated_band": task_response if skill == "task_response" else other,
            "evidence_count": 3,
            "last_evidence_id": index,
            "state_policy_version": "writing-state-ewma-v1",
            "revision": 3,
            "updated_at": updated_at,
        }
        for index, skill in enumerate(
            (
                "task_response",
                "coherence_and_cohesion",
                "lexical_resource",
                "grammatical_range_and_accuracy",
            ),
            start=1,
        )
    }


def _recommendation(
    *,
    decision_type: str = "practice",
    target_skill: str | None = "task_response",
    current_estimate: Decimal | None = Decimal("6.25"),
    reason_codes: list[str] | None = None,
    state_snapshot: dict[str, object] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=10,
        decision_type=decision_type,
        target_skill=target_skill,
        learner_target_band=Decimal("7.0"),
        current_estimate=current_estimate,
        reason_codes=reason_codes or ["largest_target_gap"],
        planner_version="writing-practice-gap-v1",
        state_snapshot=state_snapshot or _snapshot(task_response="6.25", other="7.00"),
        planner_context_snapshot=None,
    )


def test_no_accepted_update_returns_safe_empty_provider_free_response() -> None:
    response = WritingGuidanceService(_Session(_learner())).get(learner_id=1)
    assert response.current_recommendation is None
    assert response.guidance_items == ()
    assert response.source_citations == ()
    assert all(value is None for value in response.learner_state.current_estimates.values())


def test_practice_recommendation_uses_chronology_bound_snapshot_and_citations() -> None:
    recommendation = _recommendation()
    response = WritingGuidanceService(
        _Session(_learner(), SimpleNamespace(id=9), recommendation)
    ).get(learner_id=1)

    assert response.current_recommendation is not None
    assert response.learner_state.current_estimates["task_response"] == Decimal("6.25")
    assert response.guidance_items[0].criterion == "task_response"
    assert response.guidance_items[0].citations == response.source_citations
    assert tuple(
        link.knowledge_id for link in response.guidance_items[0].wiki_pages
    ) == response.guidance_items[0].knowledge_ids
    assert response.guidance_items[0].wiki_pages[0].page_id.startswith(
        "writing-task2-task-response-band-"
    )
    assert all(citation.source_id.startswith("ielts-") for citation in response.source_citations)


def test_guidance_wiki_links_preserve_order_deduplicate_and_fail_closed() -> None:
    links = _wiki_page_links(
        (
            "writing-task-response-band-7",
            "writing-task-response-criterion",
            "writing-task-response-band-7",
        )
    )
    assert tuple(link.page_id for link in links) == (
        "writing-task2-task-response-band-7",
        "writing-task2-task-response",
    )
    with pytest.raises(LearningPersistenceError):
        _wiki_page_links(("unknown-knowledge-id",))


def test_no_practice_uses_snapshot_but_does_not_invent_a_training_target() -> None:
    recommendation = _recommendation(
        decision_type="no_practice",
        target_skill=None,
        current_estimate=None,
        reason_codes=["target_achieved"],
        state_snapshot=_snapshot(task_response="7.00", other="7.00"),
    )
    response = WritingGuidanceService(
        _Session(_learner(), SimpleNamespace(id=9), recommendation)
    ).get(learner_id=1)

    assert response.guidance_items == ()
    assert response.current_recommendation.target_skill is None
    assert set(response.learner_state.current_estimates.values()) == {Decimal("7.00")}


def test_corrupt_authoritative_snapshot_fails_safely() -> None:
    recommendation = _recommendation(state_snapshot={"task_response": {}})
    with pytest.raises(LearningPersistenceError, match="snapshot is invalid"):
        WritingGuidanceService(
            _Session(_learner(), SimpleNamespace(id=9), recommendation)
        ).get(learner_id=1)


def test_unknown_learner_is_not_found() -> None:
    with pytest.raises(LearnerNotFoundError):
        WritingGuidanceService(_Session(None)).get(learner_id=1)
