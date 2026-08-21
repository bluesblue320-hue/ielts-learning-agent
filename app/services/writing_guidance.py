"""Deterministic, provider-free grounded Writing guidance."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.knowledge.retriever import retrieve_knowledge
from app.knowledge.sources import KNOWLEDGE_SOURCES
from app.models.learning import Learner, LearnerSkillState, LearningUpdate, PracticeRecommendation
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
            estimates = {
                row.skill: row.estimated_band
                for row in self._session.scalars(
                    select(LearnerSkillState).where(LearnerSkillState.learner_id == learner_id)
                ).all()
            }
            state = GroundedLearnerStateSummary(
                learner_id=learner.id,
                writing_target_band=BandScore(value=learner.writing_target_band),
                current_estimates={
                    skill: estimates.get(skill)
                    for skill in _CHINESE_CRITERION_LABELS
                },
            )
            update = self._session.scalar(
                select(LearningUpdate)
                .where(LearningUpdate.learner_id == learner_id)
                .order_by(LearningUpdate.id.desc())
            )
            if update is None:
                return WritingGroundedGuidanceResponse(learner_state=state)
            recommendation = self._session.scalar(
                select(PracticeRecommendation).where(
                    PracticeRecommendation.learning_update_id == update.id,
                    PracticeRecommendation.learner_id == learner_id,
                )
            )
            if recommendation is None:
                raise LearningPersistenceError("accepted update has no recommendation")
            summary = GroundedRecommendationSummary(
                id=recommendation.id,
                decision_type=recommendation.decision_type,
                target_skill=recommendation.target_skill,
                learner_target_band=(BandScore(value=recommendation.learner_target_band) if recommendation.learner_target_band is not None else None),
                current_estimate=recommendation.current_estimate,
                reason_codes=tuple(recommendation.reason_codes),
            )
            if recommendation.decision_type != "practice" or recommendation.target_skill is None:
                return WritingGroundedGuidanceResponse(
                    learner_state=state, current_recommendation=summary
                )
            estimate = estimates.get(recommendation.target_skill)
            if estimate is None or recommendation.learner_target_band is None:
                return WritingGroundedGuidanceResponse(
                    learner_state=state, current_recommendation=summary
                )
            result = retrieve_knowledge(
                KnowledgeRetrievalQuery(
                    purpose=KnowledgeRetrievalPurpose.LEARNER_GUIDANCE,
                    criterion=recommendation.target_skill,
                    current_band=_nearest_half_band(estimate),
                    target_band=BandScore(value=recommendation.learner_target_band),
                )
            )
        except LearnerNotFoundError:
            raise
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
                    citations.append(GroundedCitation(
                        source_id=source.source_id, publisher=source.publisher,
                        title=source.title, url=source.url, locator=reference.locator,
                        page=reference.page, section=reference.section,
                    ))
        label = _CHINESE_CRITERION_LABELS[recommendation.target_skill]
        item = GroundedGuidanceItem(
            criterion=recommendation.target_skill,
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
