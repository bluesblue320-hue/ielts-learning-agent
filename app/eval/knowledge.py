"""Deterministic Phase 9 Knowledge grounding verification for P10-07."""

from app.knowledge.retriever import retrieve_knowledge
from app.knowledge.sources import KNOWLEDGE_SOURCES
from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS, validate_snapshot_integrity
from app.schemas.knowledge import KnowledgeRetrievalQuery

from app.eval.schemas import (
    EvalFinding,
    EvalSeverity,
    EvalStatus,
    EvaluatorId,
    FailureBoundary,
)


def evaluate_knowledge_grounding(
    *,
    knowledge_ids: tuple[str, ...],
    query: KnowledgeRetrievalQuery | None = None,
) -> EvalFinding:
    """Verify snapshot-owned identities, provenance, and retrieval determinism."""

    try:
        validate_snapshot_integrity()
    except ValueError:
        return _failure("knowledge_snapshot_integrity", EvalSeverity.VETO)

    units = {unit.knowledge_id: unit for unit in WRITING_TASK2_KNOWLEDGE_UNITS}
    for knowledge_id in knowledge_ids:
        unit = units.get(knowledge_id)
        if unit is None:
            return _failure("knowledge_unknown_id", EvalSeverity.VETO)
        if any(reference.source_id not in KNOWLEDGE_SOURCES or not reference.locator for reference in unit.source_refs):
            return _failure("knowledge_unknown_provenance", EvalSeverity.VETO)

    if query is not None:
        first = tuple(unit.knowledge_id for unit in retrieve_knowledge(query).units)
        second = tuple(unit.knowledge_id for unit in retrieve_knowledge(query).units)
        if first != second:
            return _failure("knowledge_retrieval_not_deterministic", EvalSeverity.MAJOR)

    return EvalFinding(
        evaluator=EvaluatorId.KNOWLEDGE_GROUNDING,
        status=EvalStatus.PASS,
        severity=EvalSeverity.INFO,
    )


def _failure(code: str, severity: EvalSeverity) -> EvalFinding:
    return EvalFinding(
        evaluator=EvaluatorId.KNOWLEDGE_GROUNDING,
        status=EvalStatus.FAIL,
        severity=severity,
        first_failing_boundary=FailureBoundary.KNOWLEDGE,
        failure_codes=(code,),
    )


__all__ = ["evaluate_knowledge_grounding"]
