"""Decision-gated, success-only Phase 4 practice generation (P4-09)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.llm.practice_generator import PracticeGenerationRequest, PracticeGenerator
from app.models.learning import Learner, LearningUpdate, PracticeRecommendation
from app.models.practice import WritingPractice
from app.schemas.practice import (
    GeneratedWritingPractice,
    GenerationOutcome,
    PracticeLifecycleState,
    PracticeResponse,
)


GENERATION_POLICY_VERSION = "writing-practice-generation-v1"
PRACTICE_PROMPT_VERSION = "practice-generation-v1"
PRACTICE_IDEMPOTENCY_CONSTRAINT = "uq_writing_practice_recommendation_id"


@dataclass(frozen=True)
class AgentGenerationOutcome:
    """Private result for an Agent-only current-update generation fence."""

    status: Literal["generated", "resolved", "stale_discarded"]
    practice: PracticeResponse | None = None


class PracticeGenerationError(Exception):
    """Base error for practice-generation application outcomes."""


class RecommendationNotFoundError(PracticeGenerationError):
    """The referenced persisted recommendation does not exist."""


class RecommendationOwnershipError(PracticeGenerationError):
    """The recommendation is owned by a different learner."""


class PracticeGenerationPersistenceError(PracticeGenerationError):
    """An unexpected persistence failure occurred during generation."""


class GeneratedPracticeAuthorityError(PracticeGenerationError):
    """A generator returned content that conflicts with recommendation authority."""


def _practice_response(practice: WritingPractice) -> PracticeResponse:
    return PracticeResponse(
        id=practice.id,
        learner_id=practice.learner_id,
        recommendation_id=practice.recommendation_id,
        target_skill=practice.target_skill,
        question=practice.question,
        focus_objective=practice.focus_objective,
        instructions=list(practice.instructions),
        checkpoints=list(practice.checkpoints),
        practice_type=practice.practice_type,
        generator_policy_version=practice.generator_policy_version,
        provider=practice.provider,
        model=practice.model,
        prompt_version=practice.prompt_version,
        thinking_mode=practice.thinking_mode,
        lifecycle_state=PracticeLifecycleState(practice.lifecycle_state),
        attempt_id=practice.attempt_id,
        created_at=practice.created_at,
        updated_at=practice.updated_at,
    )


def _new_practice(
    *,
    learner_id: int,
    recommendation_id: int,
    target_skill: str,
    generated: GeneratedWritingPractice,
) -> WritingPractice:
    return WritingPractice(
        learner_id=learner_id,
        recommendation_id=recommendation_id,
        target_skill=target_skill,
        practice_type=generated.practice_type,
        question=generated.question,
        focus_objective=generated.focus_objective,
        instructions=list(generated.instructions),
        checkpoints=list(generated.checkpoints),
        generator_policy_version=generated.generator_policy_version,
        provider=generated.provider,
        model=generated.model,
        prompt_version=generated.prompt_version,
        thinking_mode=generated.thinking_mode,
        lifecycle_state=PracticeLifecycleState.GENERATED.value,
    )


def _violated_constraint(error: IntegrityError) -> str | None:
    diag = getattr(error.orig, "diag", None)
    return getattr(diag, "constraint_name", None)


def _existing_practice(
    session: Session,
    recommendation_id: int,
) -> WritingPractice | None:
    return session.scalar(
        select(WritingPractice).where(
            WritingPractice.recommendation_id == recommendation_id
        )
    )


class PracticeGenerationService:
    """Resolve one recommendation into at most one durable practice.

    The provider call happens after all read transactions are released and
    before the short insert transaction begins. A concurrent insert loser
    resolves and returns the persisted unique-constraint winner.
    """

    def __init__(self, session: Session, generator: PracticeGenerator) -> None:
        self._session = session
        self._generator = generator

    async def generate_or_resolve(
        self,
        *,
        learner_id: int,
        recommendation_id: int,
    ) -> GenerationOutcome:
        recommendation = self._load_recommendation(
            learner_id=learner_id,
            recommendation_id=recommendation_id,
        )
        existing = self._resolve_existing(recommendation.id)
        if existing is not None:
            return GenerationOutcome(decision="practice", practice=_practice_response(existing))

        if recommendation.decision_type == "no_practice":
            return GenerationOutcome(
                decision="no_practice",
                no_practice_reasons=list(recommendation.reason_codes),
            )

        if recommendation.target_skill is None:
            raise PracticeGenerationPersistenceError(
                "persisted practice recommendation has no target skill"
            )
        recommendation_id = recommendation.id
        target_skill = recommendation.target_skill
        generated = await self._generate_outside_transaction(recommendation)
        # The recommendation may have been refreshed while building the
        # generator request. The insert uses captured authority scalars, so
        # this rollback cannot trigger another ORM refresh before persistence.
        self._session.rollback()
        practice = self._persist_or_resolve_winner(
            learner_id=learner_id,
            recommendation_id=recommendation_id,
            target_skill=target_skill,
            generated=generated,
        )
        return GenerationOutcome(decision="practice", practice=_practice_response(practice))

    async def generate_or_resolve_current(
        self,
        *,
        learner_id: int,
        recommendation_id: int,
        expected_learning_update_id: int,
    ) -> AgentGenerationOutcome:
        """Generate only while the observed update/recommendation remains current."""

        recommendation = self._load_recommendation(
            learner_id=learner_id, recommendation_id=recommendation_id
        )
        if not self._agent_recommendation_is_current(
            learner_id=learner_id,
            recommendation_id=recommendation.id,
            expected_learning_update_id=expected_learning_update_id,
        ):
            return AgentGenerationOutcome(status="stale_discarded")
        existing = self._resolve_existing(recommendation.id)
        if existing is not None:
            return AgentGenerationOutcome(
                status="resolved", practice=_practice_response(existing)
            )
        if recommendation.decision_type == "no_practice":
            return AgentGenerationOutcome(status="stale_discarded")
        if recommendation.target_skill is None:
            raise PracticeGenerationPersistenceError(
                "persisted practice recommendation has no target skill"
            )
        captured_recommendation_id = recommendation.id
        target_skill = recommendation.target_skill
        generated = await self._generate_outside_transaction(recommendation)
        self._session.rollback()
        persisted = self._persist_if_agent_current(
            learner_id=learner_id,
            recommendation_id=captured_recommendation_id,
            expected_learning_update_id=expected_learning_update_id,
            target_skill=target_skill,
            generated=generated,
        )
        if persisted is None:
            return AgentGenerationOutcome(status="stale_discarded")
        practice, resolved = persisted
        return AgentGenerationOutcome(
            status="resolved" if resolved else "generated",
            practice=_practice_response(practice),
        )

    def _agent_recommendation_is_current(
        self,
        *,
        learner_id: int,
        recommendation_id: int,
        expected_learning_update_id: int,
    ) -> bool:
        try:
            latest_id = self._session.scalar(
                select(LearningUpdate.id)
                .where(LearningUpdate.learner_id == learner_id)
                .order_by(LearningUpdate.id.desc())
                .limit(1)
            )
            current = self._session.scalar(
                select(PracticeRecommendation.id).where(
                    PracticeRecommendation.id == recommendation_id,
                    PracticeRecommendation.learner_id == learner_id,
                    PracticeRecommendation.learning_update_id == expected_learning_update_id,
                )
            )
            self._session.rollback()
            return latest_id == expected_learning_update_id and current is not None
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PracticeGenerationPersistenceError(
                "agent generation freshness check failed"
            ) from error

    def _persist_if_agent_current(
        self,
        *,
        learner_id: int,
        recommendation_id: int,
        expected_learning_update_id: int,
        target_skill: str,
        generated: GeneratedWritingPractice,
    ) -> tuple[WritingPractice, bool] | None:
        try:
            with self._session.begin():
                learner = self._session.scalar(
                    select(Learner).where(Learner.id == learner_id).with_for_update()
                )
                if learner is None:
                    raise RecommendationNotFoundError("learner was not found")
                latest_id = self._session.scalar(
                    select(LearningUpdate.id)
                    .where(LearningUpdate.learner_id == learner_id)
                    .order_by(LearningUpdate.id.desc())
                    .limit(1)
                )
                current = self._session.scalar(
                    select(PracticeRecommendation).where(
                        PracticeRecommendation.id == recommendation_id,
                        PracticeRecommendation.learner_id == learner_id,
                        PracticeRecommendation.learning_update_id == expected_learning_update_id,
                    )
                )
                if latest_id != expected_learning_update_id or current is None:
                    return None
                existing = _existing_practice(self._session, recommendation_id)
                if existing is not None:
                    return existing, True
                practice = _new_practice(
                    learner_id=learner_id,
                    recommendation_id=recommendation_id,
                    target_skill=target_skill,
                    generated=generated,
                )
                self._session.add(practice)
                self._session.flush()
                return practice, False
        except IntegrityError as error:
            self._session.rollback()
            if _violated_constraint(error) != PRACTICE_IDEMPOTENCY_CONSTRAINT:
                raise PracticeGenerationPersistenceError(
                    "writing practice could not be persisted"
                ) from error
            winner = _existing_practice(self._session, recommendation_id)
            self._session.rollback()
            if winner is None:
                raise PracticeGenerationPersistenceError(
                    "writing practice winner could not be resolved"
                ) from error
            return winner, True
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PracticeGenerationPersistenceError(
                "agent generation persistence failure"
            ) from error

    def _load_recommendation(
        self,
        *,
        learner_id: int,
        recommendation_id: int,
    ) -> PracticeRecommendation:
        try:
            recommendation = self._session.get(PracticeRecommendation, recommendation_id)
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PracticeGenerationPersistenceError(
                "practice recommendation persistence failure"
            ) from error
        if recommendation is None:
            self._session.rollback()
            raise RecommendationNotFoundError("practice recommendation was not found")
        if recommendation.learner_id != learner_id:
            self._session.rollback()
            raise RecommendationOwnershipError(
                "practice recommendation belongs to another learner"
            )
        return recommendation

    def _resolve_existing(self, recommendation_id: int) -> WritingPractice | None:
        try:
            existing = _existing_practice(self._session, recommendation_id)
            # Never hold the implicit read transaction across an async provider call.
            self._session.rollback()
            return existing
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PracticeGenerationPersistenceError(
                "writing practice persistence failure"
            ) from error

    async def _generate_outside_transaction(
        self,
        recommendation: PracticeRecommendation,
    ) -> GeneratedWritingPractice:
        request = PracticeGenerationRequest(
            recommendation_id=recommendation.id,
            decision_type="practice",
            target_skill=recommendation.target_skill,
            learner_target_band=(
                Decimal(recommendation.learner_target_band)
                if recommendation.learner_target_band is not None
                else None
            ),
            reason_codes=list(recommendation.reason_codes),
            planner_version=recommendation.planner_version,
            generator_policy_version=GENERATION_POLICY_VERSION,
            prompt_version=PRACTICE_PROMPT_VERSION,
        )
        # Attribute reads above can refresh an expired ORM row after the
        # idempotency lookup. Release that implicit read transaction before the
        # network-bound generator is awaited.
        self._session.rollback()
        generated = await self._generator.generate_practice(request)
        if generated.target_skill != recommendation.target_skill:
            raise GeneratedPracticeAuthorityError(
                "generator returned a different target skill"
            )
        return generated

    def _persist_or_resolve_winner(
        self,
        *,
        learner_id: int,
        recommendation_id: int,
        target_skill: str,
        generated: GeneratedWritingPractice,
    ) -> WritingPractice:
        practice = _new_practice(
            learner_id=learner_id,
            recommendation_id=recommendation_id,
            target_skill=target_skill,
            generated=generated,
        )
        try:
            with self._session.begin():
                self._session.add(practice)
                self._session.flush()
            return practice
        except IntegrityError as error:
            self._session.rollback()
            if _violated_constraint(error) != PRACTICE_IDEMPOTENCY_CONSTRAINT:
                raise PracticeGenerationPersistenceError(
                    "writing practice could not be persisted"
                ) from error
            try:
                winner = _existing_practice(self._session, recommendation_id)
                self._session.rollback()
            except SQLAlchemyError as resolve_error:
                self._session.rollback()
                raise PracticeGenerationPersistenceError(
                    "writing practice persistence failure"
                ) from resolve_error
            if winner is None:
                raise PracticeGenerationPersistenceError(
                    "writing practice winner could not be resolved"
                ) from error
            return winner
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PracticeGenerationPersistenceError(
                "writing practice could not be persisted"
            ) from error
