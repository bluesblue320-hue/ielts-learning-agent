"""Deterministic cross-layer evidence evaluation for the frozen Writing loop."""

from datetime import datetime

from pydantic import Field, model_validator

from app.eval.knowledge import GroundingEvidence, evaluate_knowledge_grounding
from app.eval.schemas import (
    EvalFinding,
    EvalSchema,
    EvalSeverity,
    EvalStatus,
    EvaluatorId,
    FailureBoundary,
)


class OrderedLifecycleRecord(EvalSchema):
    """One durable application row with its frozen chronology fields."""

    id: int = Field(gt=0)
    created_at: datetime


class LifecycleEvidence(EvalSchema):
    """Test-side evidence assembled from persisted rows and public read models."""

    learner_id: int = Field(gt=0)
    writing_evaluation_ids: tuple[int, ...] = Field(min_length=2)
    learning_updates: tuple[OrderedLifecycleRecord, ...] = Field(min_length=2)
    learning_update_evaluation_ids: tuple[int, ...] = Field(min_length=2)
    attempts_in_state_order: tuple[OrderedLifecycleRecord, ...] = Field(min_length=2)
    state_last_attempt_id: int = Field(gt=0)
    memory_update_ids: tuple[int, ...] = Field(min_length=2)
    current_learning_update_id: int = Field(gt=0)
    recommendation_id: int = Field(gt=0)
    recommendation_learner_id: int = Field(gt=0)
    recommendation_learning_update_id: int = Field(gt=0)
    practice_id: int | None = Field(default=None, gt=0)
    practice_learner_id: int | None = Field(default=None, gt=0)
    practice_recommendation_id: int | None = Field(default=None, gt=0)
    knowledge_ids: tuple[str, ...] = ()
    grounding_evidence: GroundingEvidence | None = None
    replay_duplicate_effects: int = Field(default=0, ge=0)
    read_counts_before: tuple[int, int, int] = (0, 0, 0)
    read_counts_after: tuple[int, int, int] = (0, 0, 0)

    @model_validator(mode="after")
    def paired_lifecycle_evidence_is_complete(self) -> "LifecycleEvidence":
        if len(self.learning_updates) != len(self.learning_update_evaluation_ids):
            raise ValueError("Each LearningUpdate requires one evaluation identity.")
        if self.practice_id is None and any(
            value is not None
            for value in (self.practice_learner_id, self.practice_recommendation_id)
        ):
            raise ValueError("Practice ownership evidence requires a practice ID.")
        return self


def evaluate_lifecycle(evidence: LifecycleEvidence) -> EvalFinding:
    """Return the first actual cross-layer lifecycle contract violation."""

    if len(evidence.writing_evaluation_ids) != len(set(evidence.writing_evaluation_ids)):
        return _failure(FailureBoundary.EVALUATION, "duplicate_writing_evaluation", EvalSeverity.VETO)
    if tuple(evidence.learning_update_evaluation_ids) != tuple(evidence.writing_evaluation_ids):
        return _failure(FailureBoundary.LEARNING_UPDATE, "learning_update_evaluation_mismatch", EvalSeverity.VETO)
    update_ids = tuple(update.id for update in evidence.learning_updates)
    if len(update_ids) != len(set(update_ids)) or evidence.replay_duplicate_effects != 0:
        return _failure(FailureBoundary.LEARNING_UPDATE, "idempotent_replay_duplicate_mutation", EvalSeverity.VETO)

    canonical_attempts = tuple(
        item.id for item in sorted(evidence.attempts_in_state_order, key=lambda item: (item.created_at, item.id))
    )
    if tuple(item.id for item in evidence.attempts_in_state_order) != canonical_attempts:
        return _failure(FailureBoundary.STATE, "state_chronology_mismatch", EvalSeverity.MAJOR)
    if evidence.state_last_attempt_id != canonical_attempts[-1]:
        return _failure(FailureBoundary.STATE, "state_last_attempt_mismatch", EvalSeverity.MAJOR)

    memory_order = tuple(
        item.id for item in sorted(evidence.learning_updates, key=lambda item: (item.created_at, item.id), reverse=True)
    )
    if evidence.memory_update_ids != memory_order:
        return _failure(FailureBoundary.MEMORY, "memory_chronology_mismatch", EvalSeverity.MAJOR)
    if evidence.memory_update_ids != tuple(update_ids[index] for index in sorted(range(len(update_ids)), key=lambda index: (evidence.learning_updates[index].created_at, evidence.learning_updates[index].id), reverse=True)):
        return _failure(FailureBoundary.MEMORY, "memory_durable_update_mismatch", EvalSeverity.MAJOR)

    if evidence.current_learning_update_id != max(update_ids):
        return _failure(FailureBoundary.RECOMMENDATION, "current_update_chronology_mismatch", EvalSeverity.VETO)
    if (
        evidence.recommendation_learner_id != evidence.learner_id
        or evidence.recommendation_learning_update_id != evidence.current_learning_update_id
    ):
        return _failure(FailureBoundary.RECOMMENDATION, "recommendation_ownership_mismatch", EvalSeverity.VETO)
    if evidence.practice_id is not None and (
        evidence.practice_learner_id != evidence.learner_id
        or evidence.practice_recommendation_id != evidence.recommendation_id
    ):
        return _failure(FailureBoundary.PRACTICE_GENERATION, "practice_ownership_mismatch", EvalSeverity.VETO)
    if evidence.grounding_evidence is not None:
        grounding = evaluate_knowledge_grounding(
            knowledge_ids=evidence.knowledge_ids,
            evidence=evidence.grounding_evidence,
        )
        if grounding.status == EvalStatus.FAIL:
            return EvalFinding(
                evaluator=EvaluatorId.LIFECYCLE,
                status=EvalStatus.FAIL,
                severity=grounding.severity,
                first_failing_boundary=grounding.first_failing_boundary,
                failure_codes=grounding.failure_codes,
            )
    if evidence.read_counts_before != evidence.read_counts_after:
        return _failure(FailureBoundary.INFRASTRUCTURE, "deterministic_read_mutated_state", EvalSeverity.VETO)
    return EvalFinding(
        evaluator=EvaluatorId.LIFECYCLE,
        status=EvalStatus.PASS,
        severity=EvalSeverity.INFO,
    )


def _failure(boundary: FailureBoundary, code: str, severity: EvalSeverity) -> EvalFinding:
    return EvalFinding(
        evaluator=EvaluatorId.LIFECYCLE,
        status=EvalStatus.FAIL,
        severity=severity,
        first_failing_boundary=boundary,
        failure_codes=(code,),
    )


__all__ = ["LifecycleEvidence", "OrderedLifecycleRecord", "evaluate_lifecycle"]