"""Deterministic Phase 9 Knowledge grounding verification for P10-07."""

from pydantic import Field

from app.knowledge.retriever import retrieve_knowledge
from app.knowledge.sources import KNOWLEDGE_SOURCES
from app.knowledge.writing_task2_v1 import (
    WRITING_TASK2_KNOWLEDGE_UNITS,
    validate_snapshot_integrity,
)
from app.schemas.knowledge import (
    GroundedCitation,
    GroundedRecommendationSummary,
    KnowledgeRetrievalPurpose,
    KnowledgeRetrievalQuery,
)

from app.eval.schemas import (
    EvalFinding,
    EvalSchema,
    EvalSeverity,
    EvalStatus,
    EvaluatorId,
    FailureBoundary,
)


class GroundingEvidence(EvalSchema):
    """Test-owned, application-shaped grounding evidence without production tracing."""

    learner_id: int = Field(gt=0)
    current_learning_update_id: int = Field(gt=0)
    recommendation_learner_id: int = Field(gt=0)
    recommendation_learning_update_id: int = Field(gt=0)
    recommendation: GroundedRecommendationSummary
    query: KnowledgeRetrievalQuery
    knowledge_ids: tuple[str, ...] = Field(min_length=1)
    citations: tuple[GroundedCitation, ...] = Field(default=())
    citation_owner: str = "application"


def evaluate_knowledge_grounding(
    *,
    knowledge_ids: tuple[str, ...],
    query: KnowledgeRetrievalQuery | None = None,
    evidence: GroundingEvidence | None = None,
) -> EvalFinding:
    """Verify snapshot identity, citation ownership, context, and repeatability."""

    try:
        validate_snapshot_integrity()
    except ValueError:
        return _failure("knowledge_snapshot_integrity", EvalSeverity.VETO)

    units = {unit.knowledge_id: unit for unit in WRITING_TASK2_KNOWLEDGE_UNITS}
    for knowledge_id in knowledge_ids:
        unit = units.get(knowledge_id)
        if unit is None:
            return _failure("knowledge_unknown_id", EvalSeverity.VETO)
        if any(
            reference.source_id not in KNOWLEDGE_SOURCES or not reference.locator
            for reference in unit.source_refs
        ):
            return _failure("knowledge_unknown_provenance", EvalSeverity.VETO)

    effective_query = query
    if evidence is not None:
        if tuple(knowledge_ids) != evidence.knowledge_ids:
            return _failure("knowledge_evidence_identity_mismatch", EvalSeverity.VETO)
        if evidence.citation_owner != "application":
            return _failure("knowledge_provider_invented_citation", EvalSeverity.VETO)
        if (
            evidence.learner_id != evidence.recommendation_learner_id
            or evidence.current_learning_update_id
            != evidence.recommendation_learning_update_id
            or evidence.recommendation.id <= 0
        ):
            return _failure("knowledge_recommendation_context_mismatch", EvalSeverity.VETO)
        effective_query = evidence.query
        recommendation = evidence.recommendation
        if evidence.query.purpose == KnowledgeRetrievalPurpose.LEARNER_GUIDANCE:
            if (
                recommendation.decision_type != "practice"
                or recommendation.target_skill is None
                or recommendation.learner_target_band is None
                or evidence.query.criterion != recommendation.target_skill
                or evidence.query.target_band != recommendation.learner_target_band
            ):
                return _failure("knowledge_recommendation_context_mismatch", EvalSeverity.VETO)
            expected_citations = {
                (reference.source_id, reference.locator)
                for knowledge_id in knowledge_ids
                for reference in units[knowledge_id].source_refs
            }
            observed_citations = set()
            for citation in evidence.citations:
                source = KNOWLEDGE_SOURCES.get(citation.source_id)
                if source is None or (citation.source_id, citation.locator) not in expected_citations:
                    return _failure("knowledge_unknown_citation", EvalSeverity.VETO)
                if (citation.publisher, citation.title, citation.url) != (
                    source.publisher,
                    source.title,
                    source.url,
                ):
                    return _failure("knowledge_provider_invented_citation", EvalSeverity.VETO)
                observed_citations.add((citation.source_id, citation.locator))
            if observed_citations != expected_citations:
                return _failure("knowledge_citation_coverage_mismatch", EvalSeverity.VETO)
        elif evidence.query.purpose == KnowledgeRetrievalPurpose.PRACTICE_GENERATION:
            if (
                recommendation.decision_type != "practice"
                or recommendation.target_skill is None
                or recommendation.learner_target_band is None
                or evidence.query.criterion != recommendation.target_skill
                or evidence.query.target_band != recommendation.learner_target_band
            ):
                return _failure("knowledge_recommendation_context_mismatch", EvalSeverity.VETO)
            retrieved_ids = {
                unit.knowledge_id
                for unit in retrieve_knowledge(effective_query).units
            }
            if not set(knowledge_ids).issubset(retrieved_ids):
                return _failure("knowledge_practice_scope_mismatch", EvalSeverity.MAJOR)
        else:
            return _failure("knowledge_recommendation_context_mismatch", EvalSeverity.VETO)

    if effective_query is not None:
        first = tuple(unit.knowledge_id for unit in retrieve_knowledge(effective_query).units)
        second = tuple(unit.knowledge_id for unit in retrieve_knowledge(effective_query).units)
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


__all__ = ["GroundingEvidence", "evaluate_knowledge_grounding"]