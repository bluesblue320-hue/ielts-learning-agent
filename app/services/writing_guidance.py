"""Deterministic, provider-free grounded Writing guidance."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.knowledge.retriever import retrieve_knowledge
from app.knowledge.sources import KNOWLEDGE_SOURCES
from app.learner.planning_reconstruction import (
    PersistedPlanningReconstructionError,
    reconstruct_persisted_planning_record,
)
from app.models.learning import Learner, LearningUpdate, PracticeRecommendation
from app.schemas.common import BandScore
from app.schemas.knowledge import (
    GroundedCitation,
    GroundedGuidanceItem,
    GroundedLearnerStateSummary,
    GroundedRecommendationSummary,
    KnowledgeRetrievalPurpose,
    KnowledgeRetrievalQuery,
    WritingGroundedGuidanceResponse,
)
from app.services.learning_application import LearnerNotFoundError, LearningPersistenceError


_CHINESE_CRITERION_LABELS = {
    "task_response": "任务回应（Task Response）",
    "coherence_and_cohesion": "连贯与衔接（Coherence and Cohesion）",
    "lexical_resource": "词汇资源（Lexical Resource）",
    "grammatical_range_and_accuracy": "语法多样性与准确性（Grammatical Range and Accuracy）",
}


def _nearest_half_band(value: Decimal) -> BandScore:
    """Make a presentation-only, deterministic descriptor query value."""
    rounded = (value * 2).quantize(Decimal("1"), rounding=ROUND_HALF_UP) / 2
    return BandScore(value=rounded)


class WritingGuidanceService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, *, learner_id: int) -> WritingGroundedGuidanceResponse:
        try:
            learner = self._session.get(Learner, learner_id)
            if learner is None:
                raise LearnerNotFoundError("learner was not found")

            update = self._session.scalar(
                select(LearningUpdate)
                .where(LearningUpdate.learner_id == learner_id)
                .order_by(LearningUpdate.id.desc())
            )
            if update is None:
                return WritingGroundedGuidanceResponse(
                    learner_state=GroundedLearnerStateSummary(
                        learner_id=learner.id,
                        writing_target_band=BandScore(value=learner.writing_target_band),
                        current_estimates={skill: None for skill in _CHINESE_CRITERION_LABELS},
                    )
                )

            recommendation = self._session.scalar(
                select(PracticeRecommendation).where(
                    PracticeRecommendation.learning_update_id == update.id,
                    PracticeRecommendation.learner_id == learner_id,
                )
            )
            if recommendation is None:
                raise LearningPersistenceError("accepted update has no recommendation")

            record = reconstruct_persisted_planning_record(recommendation)
            decision = record.decision
            estimates = {
                skill: getattr(decision.state_snapshot, skill).estimated_band
                for skill in _CHINESE_CRITERION_LABELS
            }
            target_band = (
                decision.learner_target_band.value
                if decision.learner_target_band is not None
                else learner.writing_target_band
            )
            state = GroundedLearnerStateSummary(
                learner_id=learner.id,
                writing_target_band=BandScore(value=target_band),
                current_estimates=estimates,
            )
            summary = GroundedRecommendationSummary(
                id=recommendation.id,
                decision_type=decision.decision_type,
                target_skill=decision.target_skill,
                learner_target_band=decision.learner_target_band,
                current_estimate=decision.current_estimate,
                reason_codes=tuple(code.value for code in decision.reason_codes),
            )
            if decision.decision_type != "practice" or decision.target_skill is None:
                return WritingGroundedGuidanceResponse(
                    learner_state=state, current_recommendation=summary
                )

            estimate = estimates[decision.target_skill]
            if estimate is None or decision.learner_target_band is None:
                return WritingGroundedGuidanceResponse(
                    learner_state=state, current_recommendation=summary
                )
            result = retrieve_knowledge(
                KnowledgeRetrievalQuery(
                    purpose=KnowledgeRetrievalPurpose.LEARNER_GUIDANCE,
                    criterion=decision.target_skill,
                    current_band=_nearest_half_band(estimate),
                    target_band=decision.learner_target_band,
                )
            )
        except LearnerNotFoundError:
            raise
        except PersistedPlanningReconstructionError as error:
            raise LearningPersistenceError(
                "accepted recommendation snapshot is invalid"
            ) from error
        except SQLAlchemyError as error:
            self._session.rollback()
            raise LearningPersistenceError("learning data persistence failure") from error

        citations: list[GroundedCitation] = []
        seen: set[tuple[str, str]] = set()
        for unit in result.units:
            for reference in unit.source_refs:
                source = KNOWLEDGE_SOURCES.get(reference.source_id)
                if source is None:
                    raise LearningPersistenceError("knowledge source registry is invalid")
                key = (reference.source_id, reference.locator)
                if key not in seen:
                    seen.add(key)
                    citations.append(
                        GroundedCitation(
                            source_id=source.source_id,
                            publisher=source.publisher,
                            title=source.title,
                            url=source.url,
                            locator=reference.locator,
                            page=reference.page,
                            section=reference.section,
                        )
                    )
        label = _CHINESE_CRITERION_LABELS[decision.target_skill]
        item = GroundedGuidanceItem(
            criterion=decision.target_skill,
            title=f"{label}：下一步重点",
            explanation="；".join(unit.statement for unit in result.units),
            knowledge_ids=tuple(unit.knowledge_id for unit in result.units),
            citations=tuple(citations),
        )
        return WritingGroundedGuidanceResponse(
            learner_state=state,
            current_recommendation=summary,
            guidance_items=(item,),
            source_citations=tuple(citations),
        )
