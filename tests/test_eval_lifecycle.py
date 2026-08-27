"""P10-09 deterministic lifecycle-evidence checks over frozen boundaries."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.eval.knowledge import GroundingEvidence, evaluate_knowledge_grounding
from app.eval.lifecycle import (
    LifecycleEvidence,
    OrderedLifecycleRecord,
    evaluate_lifecycle,
)
from app.knowledge.sources import KNOWLEDGE_SOURCES
from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS
from app.schemas.common import BandScore
from app.schemas.knowledge import (
    GroundedCitation,
    GroundedRecommendationSummary,
    KnowledgeRetrievalPurpose,
    KnowledgeRetrievalQuery,
)
from app.schemas.writing import WritingCriterion


def _evidence(**overrides: object) -> LifecycleEvidence:
    older = datetime(2026, 1, 1, tzinfo=UTC)
    newer = older + timedelta(days=1)
    values: dict[str, object] = {
        "learner_id": 1,
        "writing_evaluation_ids": (200, 201),
        "learning_updates": (
            OrderedLifecycleRecord(id=20, created_at=newer),
            OrderedLifecycleRecord(id=21, created_at=older),
        ),
        "learning_update_evaluation_ids": (200, 201),
        "attempts_in_state_order": (
            OrderedLifecycleRecord(id=100, created_at=older),
            OrderedLifecycleRecord(id=101, created_at=newer),
        ),
        "state_last_attempt_id": 101,
        "memory_update_ids": (20, 21),
        "current_learning_update_id": 21,
        "recommendation_id": 30,
        "recommendation_learner_id": 1,
        "recommendation_learning_update_id": 21,
        "practice_id": 40,
        "practice_learner_id": 1,
        "practice_recommendation_id": 30,
        "knowledge_ids": ("writing-task-response-band-6",),
        "read_counts_before": (2, 8, 4),
        "read_counts_after": (2, 8, 4),
    }
    values.update(overrides)
    return LifecycleEvidence.model_validate(values)


def test_canonical_multilayer_lifecycle_evidence_passes_repeatably() -> None:
    evidence = _evidence()

    assert evaluate_lifecycle(evidence) == evaluate_lifecycle(evidence)
    assert evaluate_lifecycle(evidence).status.value == "pass"


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"recommendation_learner_id": 2}, "recommendation_ownership_mismatch"),
        ({"state_last_attempt_id": 100}, "state_last_attempt_mismatch"),
        ({"memory_update_ids": (21, 20)}, "memory_chronology_mismatch"),
        ({"replay_duplicate_effects": 1}, "idempotent_replay_duplicate_mutation"),
        ({"practice_recommendation_id": 31}, "practice_ownership_mismatch"),
        ({"read_counts_after": (3, 8, 4)}, "deterministic_read_mutated_state"),
    ],
)
def test_lifecycle_negative_cases_preserve_first_failure(override: dict[str, object], code: str) -> None:
    finding = evaluate_lifecycle(_evidence(**override))

    assert finding.status.value == "fail"
    assert finding.failure_codes == (code,)


def test_lifecycle_keeps_purpose_specific_chronologies_separate() -> None:
    older = datetime(2026, 1, 1, tzinfo=UTC)
    newer = older + timedelta(days=1)
    finding = evaluate_lifecycle(
        _evidence(
            attempts_in_state_order=(
                OrderedLifecycleRecord(id=101, created_at=newer),
                OrderedLifecycleRecord(id=100, created_at=older),
            )
        )
    )

    assert finding.failure_codes == ("state_chronology_mismatch",)


def _grounding_evidence(unit, *, knowledge_ids=None) -> GroundingEvidence:
    citations = tuple(
        GroundedCitation(
            source_id=ref.source_id,
            publisher=KNOWLEDGE_SOURCES[ref.source_id].publisher,
            title=KNOWLEDGE_SOURCES[ref.source_id].title,
            url=KNOWLEDGE_SOURCES[ref.source_id].url,
            locator=ref.locator,
            page=ref.page,
            section=ref.section,
        )
        for ref in unit.source_refs
    )
    return GroundingEvidence(
        learner_id=1,
        current_learning_update_id=21,
        recommendation_learner_id=1,
        recommendation_learning_update_id=21,
        recommendation=GroundedRecommendationSummary(
            id=30,
            decision_type="practice",
            target_skill="task_response",
            learner_target_band=BandScore(value=Decimal("6.5")),
            reason_codes=("largest_target_gap",),
        ),
        query=KnowledgeRetrievalQuery(
            purpose=KnowledgeRetrievalPurpose.LEARNER_GUIDANCE,
            criterion=WritingCriterion.TASK_RESPONSE,
            current_band=BandScore(value=Decimal("6.0")),
            target_band=BandScore(value=Decimal("6.5")),
            task_type="opinion",
        ),
        knowledge_ids=knowledge_ids if knowledge_ids is not None else (unit.knowledge_id,),
        citations=citations,
    )


def test_lifecycle_with_passing_grounding_evidence_passes() -> None:
    unit = WRITING_TASK2_KNOWLEDGE_UNITS[0]
    evidence = _evidence(
        knowledge_ids=(unit.knowledge_id,),
        grounding_evidence=_grounding_evidence(unit),
    )

    assert evaluate_lifecycle(evidence).status.value == "pass"


def test_lifecycle_propagates_grounding_failure_preserving_boundary() -> None:
    unit = WRITING_TASK2_KNOWLEDGE_UNITS[0]
    other = WRITING_TASK2_KNOWLEDGE_UNITS[1]
    evidence = _evidence(
        knowledge_ids=(unit.knowledge_id,),
        grounding_evidence=_grounding_evidence(
            other, knowledge_ids=(other.knowledge_id,)
        ),
    )

    finding = evaluate_lifecycle(evidence)

    assert finding.status.value == "fail"
    assert finding.severity.value == "veto"
    assert finding.failure_codes == ("knowledge_evidence_identity_mismatch",)
    assert finding.first_failing_boundary.value == "knowledge"