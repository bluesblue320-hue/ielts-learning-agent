"""Adversarial grounding and provenance checks for Phase 9 (P9-11)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

import app.knowledge.writing_task2_v1 as snapshot
from app.knowledge.retriever import MAX_RESULTS_BY_PURPOSE, retrieve_knowledge
from app.knowledge.sources import KNOWLEDGE_SOURCES
from app.llm.deepseek import DeepSeekSettings
from app.llm.deepseek_practice import DeepSeekPracticeGenerator
from app.llm.practice_generator import (
    PracticeGenerationRequest,
    PracticeKnowledgeContext,
    PracticeKnowledgeItem,
)
from app.llm.provider import ProviderError, ProviderErrorCategory
from app.schemas.common import BandScore
from app.schemas.knowledge import (
    KnowledgeRetrievalPurpose,
    KnowledgeRetrievalQuery,
    KnowledgeSourceRef,
)
from app.services.writing_guidance import WritingGuidanceService


class _Rows:
    def __init__(self, rows: tuple[object, ...]) -> None:
        self._rows = rows

    def all(self) -> tuple[object, ...]:
        return self._rows


def _state_snapshot() -> dict[str, object]:
    return {
        skill: {
            "learner_id": 1,
            "skill": skill,
            "estimated_band": "6.25" if skill == "task_response" else "7.00",
            "evidence_count": 3,
            "last_evidence_id": index,
            "state_policy_version": "writing-state-ewma-v1",
            "revision": 3,
            "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
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


class _GuidanceSession:
    def __init__(self) -> None:
        self._scalar_calls = 0

    def get(self, _model: object, _identifier: int) -> object:
        return SimpleNamespace(id=1, writing_target_band=Decimal("7.0"))

    def scalars(self, _query: object) -> _Rows:
        return _Rows(
            (
                SimpleNamespace(
                    skill="task_response", estimated_band=Decimal("6.25")
                ),
            )
        )

    def scalar(self, _query: object) -> object:
        self._scalar_calls += 1
        if self._scalar_calls == 1:
            return SimpleNamespace(id=9)
        return SimpleNamespace(
            id=10,
            decision_type="practice",
            target_skill="task_response",
            learner_target_band=Decimal("7.0"),
            current_estimate=Decimal("6.25"),
            reason_codes=["largest_target_gap"],
            planner_version="writing-practice-gap-v1",
            state_snapshot=_state_snapshot(),
            planner_context_snapshot=None,
        )

    def rollback(self) -> None:
        raise AssertionError("grounded guidance should not roll back")


def _query() -> KnowledgeRetrievalQuery:
    return KnowledgeRetrievalQuery(
        purpose=KnowledgeRetrievalPurpose.LEARNER_GUIDANCE,
        criterion="task_response",
        current_band=BandScore(value=Decimal("6.5")),
        target_band=BandScore(value=Decimal("7.0")),
    )


def _generation_request() -> PracticeGenerationRequest:
    return PracticeGenerationRequest(
        recommendation_id=10,
        target_skill="task_response",
        learner_target_band=Decimal("7.0"),
        reason_codes=["largest_target_gap"],
        planner_version="writing-practice-gap-memory-v2",
        generator_policy_version="writing-practice-generation-v2",
        prompt_version="practice-generation-v2",
        knowledge_context=PracticeKnowledgeContext(
            items=(
                PracticeKnowledgeItem(
                    knowledge_id="writing-task-response-band-7",
                    statement="Task Response requires a developed response.",
                    source_ids=("ielts-writing-band-descriptors-2023",),
                ),
            )
        ),
    )


def _provider_response(extra_field: str) -> httpx.Response:
    content = {
        "practice_type": "targeted_task2",
        "target_skill": "task_response",
        "question": "Write an essay about public transport.",
        "focus_objective": "Develop a clear position.",
        "instructions": ["Support the position with relevant ideas."],
        "checkpoints": ["Check that the position is clear."],
        extra_field: "attacker-controlled-id",
    }
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": json.dumps(content)},
                }
            ]
        },
    )


def test_public_guidance_claims_and_citations_resolve_to_snapshot() -> None:
    response = WritingGuidanceService(_GuidanceSession()).get(learner_id=1)
    units_by_id = {
        unit.knowledge_id: unit for unit in snapshot.WRITING_TASK2_KNOWLEDGE_UNITS
    }

    assert response.guidance_items
    for item in response.guidance_items:
        units = tuple(units_by_id[knowledge_id] for knowledge_id in item.knowledge_ids)
        assert item.explanation == "；".join(unit.statement for unit in units)
        expected_refs = {
            (reference.source_id, reference.locator)
            for unit in units
            for reference in unit.source_refs
        }
        assert {
            (citation.source_id, citation.locator) for citation in item.citations
        } == expected_refs
        for citation in item.citations:
            source = KNOWLEDGE_SOURCES[citation.source_id]
            assert (citation.publisher, citation.title, citation.url) == (
                source.publisher,
                source.title,
                source.url,
            )

    public_keys = json.dumps(response.model_dump(mode="json"), sort_keys=True).lower()
    assert "chain_of_thought" not in public_keys
    assert '"reasoning"' not in public_keys


def test_snapshot_integrity_fails_closed_for_unknown_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = snapshot.WRITING_TASK2_KNOWLEDGE_UNITS[0]
    poisoned = original.model_copy(
        update={
            "source_refs": (
                KnowledgeSourceRef(
                    source_id="unknown-official-source",
                    locator="invented locator",
                ),
            )
        }
    )
    monkeypatch.setattr(
        snapshot,
        "WRITING_TASK2_KNOWLEDGE_UNITS",
        (poisoned, *snapshot.WRITING_TASK2_KNOWLEDGE_UNITS[1:]),
    )

    with pytest.raises(ValueError, match="Unknown Knowledge source"):
        snapshot.validate_snapshot_integrity()


@pytest.mark.parametrize("extra_field", ["source_id", "knowledge_id"])
def test_provider_cannot_inject_source_or_knowledge_identity(extra_field: str) -> None:
    settings = DeepSeekSettings(
        api_key="test-key",
        api_url="https://api.deepseek.test/chat/completions",
        model="test-practice-model",
        timeout_seconds=2,
        _env_file=None,
    )
    generator = DeepSeekPracticeGenerator(settings)

    with pytest.raises(ProviderError) as captured:
        generator._validated_result(
            _provider_response(extra_field), _generation_request()
        )

    assert captured.value.category is ProviderErrorCategory.INVALID_RESPONSE


def test_retrieval_rejects_arbitrary_text_and_learner_metadata() -> None:
    payload = _query().model_dump()
    payload.update(
        {
            "raw_query": "find anything about this learner",
            "learner_id": 99,
        }
    )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        KnowledgeRetrievalQuery.model_validate(payload)


def test_retrieval_is_bounded_deterministic_and_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Phase 9 retrieval must not construct an HTTP client")

    monkeypatch.setattr(httpx, "AsyncClient", fail_network)
    first = retrieve_knowledge(_query())
    second = retrieve_knowledge(_query())
    first_ids = tuple(unit.knowledge_id for unit in first.units)

    assert first_ids == tuple(unit.knowledge_id for unit in second.units)
    assert len(first_ids) <= MAX_RESULTS_BY_PURPOSE[_query().purpose]
    assert len(first_ids) == len(set(first_ids))
    assert all("band-6-5" not in knowledge_id for knowledge_id in first_ids)
    assert {
        unit.descriptor_band
        for unit in first.units
        if unit.descriptor_band is not None
    } == {6, 7}
