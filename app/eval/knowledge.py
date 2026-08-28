"""Deterministic Phase 9 Knowledge grounding verification for P10-07."""

from decimal import ROUND_HALF_UP, Decimal

from pydantic import Field

from app.knowledge.retriever import retrieve_knowledge
from app.knowledge.sources import KNOWLEDGE_SOURCES
from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS, validate_snapshot_integrity
from app.schemas.common import BandScore
from app.schemas.knowledge import (
    GroundedCitation,
    GroundedRecommendationSummary,
    KnowledgeRetrievalPurpose,
    KnowledgeRetrievalQuery,
)

from app.eval.schemas import EvalFinding, EvalSchema, EvalSeverity, EvalStatus, EvaluatorId, FailureBoundary


class GroundingEvidence(EvalSchema):
    """Test-owned application-shaped evidence for guidance or practice generation."""

    learner_id: int = Field(gt=0)
    current_learning_update_id: int = Field(gt=0)
    recommendation_learner_id: int = Field(gt=0)
    recommendation_learning_update_id: int = Field(gt=0)
    recommendation: GroundedRecommendationSummary
    query: KnowledgeRetrievalQuery
    knowledge_ids: tuple[str, ...] = Field(min_length=1)
    citations: tuple[GroundedCitation, ...] = ()
    practice_knowledge_source_ids: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    citation_owner: str = "application"


def normalize_generation_current_band(value: Decimal) -> BandScore:
    rounded = (value * 2).quantize(Decimal("1"), rounding=ROUND_HALF_UP) / 2
    return BandScore(value=rounded)


def evaluate_knowledge_grounding(*, knowledge_ids: tuple[str, ...], query: KnowledgeRetrievalQuery | None = None, evidence: GroundingEvidence | None = None) -> EvalFinding:
    """Verify snapshot identity, purpose-aware context, ownership, and repeatability."""

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

    effective_query = query
    if evidence is not None:
        failure = _validate_evidence(evidence, knowledge_ids, units)
        if failure is not None:
            return failure
        effective_query = evidence.query
    if effective_query is not None:
        first = tuple(unit.knowledge_id for unit in retrieve_knowledge(effective_query).units)
        second = tuple(unit.knowledge_id for unit in retrieve_knowledge(effective_query).units)
        if first != second:
            return _failure("knowledge_retrieval_not_deterministic", EvalSeverity.MAJOR)
        if (
            effective_query.purpose is KnowledgeRetrievalPurpose.PRACTICE_GENERATION
            and first != tuple(knowledge_ids)
        ):
            return _failure("knowledge_practice_scope_mismatch", EvalSeverity.MAJOR)
    return EvalFinding(evaluator=EvaluatorId.KNOWLEDGE_GROUNDING, status=EvalStatus.PASS, severity=EvalSeverity.INFO)


def _validate_evidence(evidence: GroundingEvidence, knowledge_ids: tuple[str, ...], units: dict[str, object]) -> EvalFinding | None:
    if tuple(knowledge_ids) != evidence.knowledge_ids:
        return _failure("knowledge_evidence_identity_mismatch", EvalSeverity.VETO)
    if evidence.citation_owner != "application":
        return _failure("knowledge_provider_invented_citation", EvalSeverity.VETO)
    recommendation = evidence.recommendation
    if (
        evidence.learner_id != evidence.recommendation_learner_id
        or evidence.current_learning_update_id != evidence.recommendation_learning_update_id
        or recommendation.id <= 0
        or recommendation.decision_type != "practice"
        or recommendation.target_skill is None
        or recommendation.learner_target_band is None
        or recommendation.current_estimate is None
        or evidence.query.purpose not in {KnowledgeRetrievalPurpose.LEARNER_GUIDANCE, KnowledgeRetrievalPurpose.PRACTICE_GENERATION}
        or evidence.query.criterion != recommendation.target_skill
        or evidence.query.target_band != recommendation.learner_target_band
        or evidence.query.current_band != normalize_generation_current_band(Decimal(recommendation.current_estimate))
    ):
        return _failure("knowledge_recommendation_context_mismatch", EvalSeverity.VETO)
    expected_refs = {
        knowledge_id: {(reference.source_id, reference.locator) for reference in units[knowledge_id].source_refs}
        for knowledge_id in knowledge_ids
    }
    if evidence.query.purpose is KnowledgeRetrievalPurpose.LEARNER_GUIDANCE:
        if not evidence.citations:
            return _failure("knowledge_citation_coverage_mismatch", EvalSeverity.VETO)
        observed = set()
        for citation in evidence.citations:
            source = KNOWLEDGE_SOURCES.get(citation.source_id)
            if source is None or not any((citation.source_id, citation.locator) in refs for refs in expected_refs.values()):
                return _failure("knowledge_unknown_citation", EvalSeverity.VETO)
            if (citation.publisher, citation.title, citation.url) != (source.publisher, source.title, source.url):
                return _failure("knowledge_provider_invented_citation", EvalSeverity.VETO)
            observed.add((citation.source_id, citation.locator))
        if observed != {item for refs in expected_refs.values() for item in refs}:
            return _failure("knowledge_citation_coverage_mismatch", EvalSeverity.VETO)
        return None
    if evidence.citations:
        return _failure("knowledge_generation_citations_not_application_shaped", EvalSeverity.VETO)
    expected_sources = {knowledge_id: tuple(reference.source_id for reference in units[knowledge_id].source_refs) for knowledge_id in knowledge_ids}
    if evidence.practice_knowledge_source_ids != expected_sources:
        return _failure("knowledge_generation_source_mismatch", EvalSeverity.VETO)
    return None


def _failure(code: str, severity: EvalSeverity) -> EvalFinding:
    return EvalFinding(evaluator=EvaluatorId.KNOWLEDGE_GROUNDING, status=EvalStatus.FAIL, severity=severity, first_failing_boundary=FailureBoundary.KNOWLEDGE, failure_codes=(code,))


__all__ = ["GroundingEvidence", "evaluate_knowledge_grounding", "normalize_generation_current_band"]