"""Official provider-free runtime for the canonical Phase 10 regression corpus."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.agent.executor import (
    MAX_MUTATING_TOOL_EXECUTIONS,
    MAX_OBSERVATIONS,
    MAX_PROVIDER_BACKED_SERVICE_INVOCATIONS,
    AgentTurnExecutor,
)
from app.agent.observation import AgentObservedState, observe_agent_state
from app.agent.selector import AgentStalePracticeError
from app.agent.tools import AgentTools
from app.db.session import create_session_factory
from app.eval.attribution import FindingEvidence
from app.eval.authority import AuthorityEvidence, evaluate_authority
from app.eval.corpora import RegressionCorpus, load_regression_corpus
from app.eval.isolation import validate_test_database_url
from app.eval.knowledge import (
    GroundingEvidence,
    evaluate_knowledge_grounding,
    normalize_generation_current_band,
)
from app.eval.lifecycle import (
    LifecycleEvidence,
    OrderedLifecycleRecord,
    evaluate_lifecycle,
)
from app.eval.outcome import evaluate_outcome
from app.eval.reporting import (
    StructuredEvalReport,
    build_structured_report,
    render_human_report,
)
from app.eval.runner import EvalRunner, RegressionExecutor, RunnerSuiteResult
from app.eval.schemas import (
    EvidenceReference,
    EvalFinding,
    EvalSeverity,
    EvalStatus,
    FailureBoundary,
    RegressionCase,
)
from app.eval.trajectory import evaluate_trajectory
from app.knowledge.retriever import retrieve_knowledge
from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS
from app.llm.practice_generator import PracticeGenerationRequest
from app.llm.provider import (
    ProviderError,
    ProviderErrorCategory,
    ProviderErrorContext,
    ThinkingMode,
    WritingProviderRequest,
)
from app.llm.retry import RetryingProvider
from app.memory.episode_queries import list_learner_episodes
from app.models.learning import (
    Learner,
    LearnerSkillState,
    LearningEvidence,
    LearningUpdate,
    PracticeRecommendation,
)
from app.models.practice import WritingPractice
from app.models.writing import WritingAttempt, WritingEvaluation
from app.schemas.agent import (
    AgentObservation,
    AgentOutcome,
    AgentTool,
    ObservationKind,
    PracticeSubmissionAgentTurn,
)
from app.schemas.common import BandScore
from app.schemas.knowledge import (
    GroundedRecommendationSummary,
    KnowledgeRetrievalPurpose,
    KnowledgeRetrievalQuery,
)
from app.schemas.practice import (
    GeneratedWritingPractice,
    PracticeLifecycleState,
    PracticeResponse,
)
from app.schemas.writing import WritingSubmission
from app.services.learning_application import apply_writing_evaluation
from app.services.practice_generation import (
    PracticeGenerationService,
    RecommendationOwnershipError,
)
from app.services.writing_evaluation import WritingEvaluationService


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "eval"
CANONICAL_CORPUS_PATH = CANONICAL_FIXTURE_ROOT / "regression_corpus.json"
REPORT_CONFIG_VERSION = "phase10-canonical-regression-runtime-v1"
_TRUNCATE_SQL = text(
    "TRUNCATE writing_practices, practice_recommendations, learner_skill_states, "
    "learning_evidence, learning_updates, learners, writing_evaluations, "
    "writing_attempts RESTART IDENTITY CASCADE"
)


class CanonicalRegistryError(ValueError):
    """The official executor registry does not exactly match the corpus."""


@dataclass(frozen=True)
class CanonicalRegressionExecution:
    """One suite plus both report representations derived from it."""

    suite: RunnerSuiteResult
    structured_report: StructuredEvalReport
    human_report: str


@dataclass(frozen=True)
class _LifecycleRun:
    evidence: LifecycleEvidence
    accepted_updates: int
    duplicate_effects: int
    state_chronology_valid: bool
    planner_stages: tuple[str, ...]
    planner_projection_valid: bool


class _FixtureWritingProvider:
    """Narrow deterministic adapter for frozen provider payloads and failures."""

    def __init__(self, effects: Iterable[object]) -> None:
        self._effects = deque(effects)
        self.requests: list[WritingProviderRequest] = []

    @property
    def provider_name(self) -> str:
        return "phase10-fixture-provider"

    @property
    def model_name(self) -> str:
        return "phase10-fixture-model"

    @property
    def thinking_mode(self) -> ThinkingMode:
        return ThinkingMode.DISABLED

    async def evaluate_writing(self, request: WritingProviderRequest):
        self.requests.append(request.model_copy(deep=True))
        if not self._effects:
            raise AssertionError("fixture provider has no scripted effect")
        effect = self._effects.popleft()
        if isinstance(effect, ProviderError):
            raise effect
        return effect


class _DeterministicPracticeGenerator:
    """Existing PracticeGenerator protocol implementation with no network access."""

    def __init__(self) -> None:
        self.requests: list[PracticeGenerationRequest] = []

    @property
    def provider_name(self) -> str:
        return "phase10-fixture-practice-provider"

    @property
    def model_name(self) -> str:
        return "phase10-fixture-practice-model"

    @property
    def thinking_mode(self) -> ThinkingMode:
        return ThinkingMode.DISABLED

    async def generate_practice(
        self, request: PracticeGenerationRequest
    ) -> GeneratedWritingPractice:
        self.requests.append(request.model_copy(deep=True))
        return GeneratedWritingPractice(
            practice_type="task2_targeted_focus",
            target_skill=request.target_skill,
            question="Some people believe public transport should receive more funding than roads. Discuss.",
            focus_objective=f"Develop a clear response focused on {request.target_skill}.",
            instructions=["Write an original IELTS Academic Writing Task 2 response."],
            checkpoints=[
                "Check that the response addresses every part of the question."
            ],
            generator_policy_version=request.generator_policy_version,
            provider=self.provider_name,
            model=self.model_name,
            prompt_version=request.prompt_version,
            thinking_mode=self.thinking_mode.value,
        )


class _ForbiddenWritingProvider(_FixtureWritingProvider):
    def __init__(self) -> None:
        super().__init__(())

    async def evaluate_writing(self, request: WritingProviderRequest):
        self.requests.append(request.model_copy(deep=True))
        raise AssertionError("canonical provider-free fence attempted a provider call")


class _BoundedAgentTools:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate_practice(self, **_kwargs):
        self.calls.append("generate")
        return SimpleNamespace(status="generated", provider_invoked=True)

    async def submit_practice(self, **_kwargs):
        self.calls.append("submit")
        return SimpleNamespace(status="submitted")

    def resolve_submitted_replay(self, **_kwargs):
        self.calls.append("resolve")
        return None

    def complete_practice(self, **_kwargs):
        self.calls.append("complete")
        return SimpleNamespace(reused=False)


def _alembic_config(database_url: str) -> Config:
    config = Config(str(REPOSITORY_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def _finding(finding: EvalFinding) -> FindingEvidence:
    return FindingEvidence(finding=finding)


def _expected_fail_closed(finding: EvalFinding, *, failure_code: str) -> EvalFinding:
    """Convert an exact real evaluator rejection into a passing regression verdict."""

    if finding.status is EvalStatus.FAIL and failure_code in finding.failure_codes:
        return EvalFinding(
            evaluator=finding.evaluator,
            status=EvalStatus.PASS,
            severity=EvalSeverity.INFO,
            evidence_references=(
                EvidenceReference(kind="expected_fail_closed", locator=failure_code),
            ),
        )
    if finding.status is EvalStatus.PASS:
        return EvalFinding(
            evaluator=finding.evaluator,
            status=EvalStatus.FAIL,
            severity=EvalSeverity.VETO,
            first_failing_boundary=FailureBoundary.KNOWLEDGE,
            failure_codes=("expected_fail_closed_rejection_missing",),
        )
    return finding


def _submission() -> WritingSubmission:
    return WritingSubmission(
        question="Some people think public transport should receive more funding than roads. Discuss both views.",
        essay="Public investment choices affect access, safety, and long-term mobility for every community.",
    )


def _load_json(path: Path) -> Mapping[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, Mapping):
        raise ValueError(f"fixture is not a JSON object: {path.name}")
    return value


def _read_counts(session: Session) -> tuple[int, int, int]:
    return (
        session.scalar(select(func.count()).select_from(LearningUpdate)) or 0,
        session.scalar(select(func.count()).select_from(LearningEvidence)) or 0,
        session.scalar(select(func.count()).select_from(LearnerSkillState)) or 0,
    )


def _add_episode(
    session: Session,
    *,
    attempt_id: int,
    evaluation_id: int,
    created_at: datetime,
    band: str,
) -> None:
    session.add(
        WritingAttempt(
            id=attempt_id,
            question="Question",
            essay="Essay",
            word_count=1,
            created_at=created_at,
        )
    )
    session.add(
        WritingEvaluation(
            id=evaluation_id,
            attempt_id=attempt_id,
            task_response_band=Decimal(band),
            coherence_and_cohesion_band=Decimal(band),
            lexical_resource_band=Decimal(band),
            grammatical_range_and_accuracy_band=Decimal(band),
            product_band=Decimal(band),
            criteria_feedback={},
            strengths=[],
            weaknesses=[],
            error_tags=[],
            recommended_skills=[],
            feedback="Feedback.",
            provider="phase10-fixture-provider",
            model="phase10-fixture-model",
            prompt_version="writing-v2",
            rubric_version="writing-task2-v1",
            scoring_policy_version="writing-product-band-v1",
            thinking_mode="disabled",
            created_at=created_at,
        )
    )


def _agent_state(kind: ObservationKind) -> AgentObservedState:
    fixed = datetime(2026, 1, 1, tzinfo=UTC)
    practice = None
    if kind in {
        ObservationKind.NEEDS_PRACTICE_SUBMISSION,
        ObservationKind.NEEDS_COMPLETION,
    }:
        practice = PracticeResponse(
            id=9,
            learner_id=1,
            recommendation_id=5,
            target_skill="task_response",
            question="Question",
            focus_objective="Objective",
            instructions=["Write."],
            checkpoints=["Check."],
            practice_type="task2_targeted_focus",
            generator_policy_version="writing-practice-generation-v2",
            provider="phase10-fixture-provider",
            model="phase10-fixture-model",
            prompt_version="practice-generation-v2",
            thinking_mode="disabled",
            lifecycle_state=PracticeLifecycleState.GENERATED,
            attempt_id=None,
            created_at=fixed,
            updated_at=fixed,
        )
    return AgentObservedState(
        observation=AgentObservation(kind=kind),
        latest_learning_update_id=4,
        recommendation_id=5,
        practice_id=9 if practice else None,
        recommendation=None,
        practice=practice,
        practice_lifecycle_state=None,
        practice_submission_fingerprint=None,
        practice_evaluation_id=None,
        practice_completion_applied=False,
    )


def validate_canonical_executor_registry(
    corpus: RegressionCorpus,
    registrations: Iterable[tuple[str, RegressionExecutor]],
) -> dict[str, RegressionExecutor]:
    """Build a registry while rejecting duplicate, missing, and unknown IDs."""

    pairs = tuple(registrations)
    registered_ids = tuple(case_id for case_id, _executor in pairs)
    if len(registered_ids) != len(set(registered_ids)):
        raise CanonicalRegistryError("duplicate canonical executor registration")
    registry = dict(pairs)
    corpus_ids = {case.case_id for case in corpus.cases}
    registered = set(registry)
    missing = sorted(corpus_ids - registered)
    unknown = sorted(registered - corpus_ids)
    if missing or unknown:
        raise CanonicalRegistryError(
            f"canonical executor registry mismatch: missing={missing}, unknown={unknown}"
        )
    return registry


class CanonicalRegressionRuntime:
    """Own the official executor registry and isolated real application paths."""

    def __init__(
        self,
        *,
        factory: sessionmaker[Session],
        fixture_root: Path = CANONICAL_FIXTURE_ROOT,
    ) -> None:
        self._factory = factory
        self._fixture_root = fixture_root

    def executors(self, corpus: RegressionCorpus) -> dict[str, RegressionExecutor]:
        registrations = (
            ("provider-invalid-structured-output", self._provider_invalid),
            ("product-band-application-authority", self._product_band),
            ("retry-exhaustion-no-write", self._retry_exhaustion),
            ("learning-update-idempotent-replay", self._idempotent_replay),
            ("state-late-arrival-canonical-rebuild", self._late_arrival),
            ("memory-planner-exact-tie", self._memory_planner_tie),
            ("recommendation-cross-learner-rejected", self._cross_learner),
            ("practice-stale-fence", self._stale_practice),
            ("knowledge-unknown-provenance-fails-closed", self._unknown_knowledge),
            ("agent-bounded-trajectory", self._bounded_agent),
            ("multi-episode-authoritative-learning-loop", self._multi_episode),
        )
        isolated = tuple(
            (case_id, self._isolated(executor)) for case_id, executor in registrations
        )
        return validate_canonical_executor_registry(corpus, isolated)

    def _isolated(self, executor: RegressionExecutor) -> RegressionExecutor:
        def execute(case: RegressionCase) -> tuple[FindingEvidence, ...]:
            self._reset_database()
            try:
                return executor(case)
            finally:
                self._reset_database()

        return execute

    def _reset_database(self) -> None:
        with self._factory() as session:
            session.execute(_TRUNCATE_SQL)
            session.commit()

    def _provider_invalid(self, case: RegressionCase) -> tuple[FindingEvidence, ...]:
        if case.provider_fixture is None:
            raise ValueError("provider fixture is required")
        provider = _FixtureWritingProvider(
            (_load_json(self._fixture_root / case.provider_fixture),)
        )
        rejected = False
        try:
            asyncio.run(WritingEvaluationService(provider).evaluate(_submission()))
        except ProviderError as error:
            rejected = error.category is ProviderErrorCategory.INVALID_RESPONSE
        observed = {
            "status": "provider_error" if rejected else "unexpected_success",
            "persistence": "none" if rejected else "unknown",
        }
        authority = AuthorityEvidence(
            authoritative_operation_succeeded=rejected,
            reported_success=rejected,
            case_valid=rejected and len(provider.requests) == 1,
        )
        return (
            _finding(evaluate_outcome(case, observed)),
            _finding(evaluate_authority(authority)),
        )

    def _product_band(self, case: RegressionCase) -> tuple[FindingEvidence, ...]:
        if case.provider_fixture is None:
            raise ValueError("provider fixture is required")
        payload = _load_json(self._fixture_root / case.provider_fixture)
        provider = _FixtureWritingProvider((payload,))
        result = asyncio.run(WritingEvaluationService(provider).evaluate(_submission()))
        criterion_values = (
            result.criteria.task_response.band.value,
            result.criteria.coherence_and_cohesion.band.value,
            result.criteria.lexical_resource.band.value,
            result.criteria.grammatical_range_and_accuracy.band.value,
        )
        application_owned = (
            "product_band" not in payload
            and result.product_band.value == sum(criterion_values) / 4
        )
        observed = {
            "product_band_owner": "application" if application_owned else "provider"
        }
        authority = AuthorityEvidence(
            authoritative_operation_succeeded=application_owned,
            reported_success=application_owned,
            application_owns_product_band=application_owned,
            case_valid=len(provider.requests) == 1,
        )
        return (
            _finding(evaluate_outcome(case, observed)),
            _finding(evaluate_authority(authority)),
        )

    def _retry_exhaustion(self, case: RegressionCase) -> tuple[FindingEvidence, ...]:
        failure = ProviderError(
            ProviderErrorCategory.TIMEOUT,
            "fixture timeout",
            context=ProviderErrorContext(provider="phase10-fixture-provider"),
        )
        provider = _FixtureWritingProvider((failure, failure, failure))

        async def no_sleep(_delay: float) -> None:
            return None

        rejected = False
        try:
            asyncio.run(
                WritingEvaluationService(
                    RetryingProvider(provider, sleeper=no_sleep)
                ).evaluate(_submission())
            )
        except ProviderError as error:
            rejected = error.category is ProviderErrorCategory.TIMEOUT
        with self._factory() as session:
            writes = (
                session.scalar(select(func.count()).select_from(WritingAttempt)) or 0
            ) + (
                session.scalar(select(func.count()).select_from(WritingEvaluation)) or 0
            )
        observed = {
            "status": "provider_error" if rejected else "unexpected_success",
            "write_count": writes,
        }
        safe = rejected and len(provider.requests) == 3 and writes == 0
        authority = AuthorityEvidence(
            authoritative_operation_succeeded=safe,
            reported_success=safe,
            case_valid=safe,
        )
        return (
            _finding(evaluate_outcome(case, observed)),
            _finding(evaluate_authority(authority)),
        )

    def _idempotent_replay(self, case: RegressionCase) -> tuple[FindingEvidence, ...]:
        with self._factory() as session:
            run = self._build_lifecycle(session)
        return (
            _finding(
                evaluate_outcome(case, {"duplicate_effects": run.duplicate_effects})
            ),
            _finding(evaluate_lifecycle(run.evidence)),
        )

    def _late_arrival(self, case: RegressionCase) -> tuple[FindingEvidence, ...]:
        with self._factory() as session:
            run = self._build_lifecycle(session)
        observed = {
            "chronology": (
                "writing_attempt_created_at_id_asc"
                if run.state_chronology_valid
                else "invalid"
            )
        }
        return (
            _finding(evaluate_outcome(case, observed)),
            _finding(evaluate_lifecycle(run.evidence)),
        )

    def _memory_planner_tie(self, case: RegressionCase) -> tuple[FindingEvidence, ...]:
        with self._factory() as session:
            run = self._build_lifecycle(session)
        expected_stages = (
            "persistent_gap",
            "trend",
            "recent_practice",
            "canonical_priority",
        )
        observed = {
            "tie_break_order": (
                "persistent_gap_trend_recency_priority"
                if run.planner_stages == expected_stages
                else "invalid"
            )
        }
        return (
            _finding(evaluate_outcome(case, observed)),
            _finding(evaluate_lifecycle(run.evidence)),
        )

    def _cross_learner(self, case: RegressionCase) -> tuple[FindingEvidence, ...]:
        with self._factory() as session:
            run = self._build_lifecycle(session)
            session.add(Learner(id=2, writing_target_band=Decimal("7.0")))
            session.commit()
            generator = _DeterministicPracticeGenerator()
            rejected = False
            try:
                asyncio.run(
                    PracticeGenerationService(session, generator).generate_or_resolve(
                        learner_id=2,
                        recommendation_id=run.evidence.recommendation_id,
                    )
                )
            except RecommendationOwnershipError:
                rejected = True
            practice_rows = (
                session.scalar(select(func.count()).select_from(WritingPractice)) or 0
            )
        observed = {
            "provider_calls": len(generator.requests),
            "practice_rows": practice_rows,
        }
        safe = rejected and not generator.requests and practice_rows == 0
        authority = AuthorityEvidence(
            authoritative_operation_succeeded=safe,
            reported_success=safe,
            case_valid=safe,
        )
        return (
            _finding(evaluate_outcome(case, observed)),
            _finding(evaluate_authority(authority)),
        )

    def _stale_practice(self, case: RegressionCase) -> tuple[FindingEvidence, ...]:
        with self._factory() as session:
            run = self._build_lifecycle(session)
            recommendation = session.get(
                PracticeRecommendation, run.evidence.recommendation_id
            )
            assert recommendation is not None
            generator = _DeterministicPracticeGenerator()
            generated = asyncio.run(
                PracticeGenerationService(
                    session, generator
                ).generate_or_resolve_current(
                    learner_id=1,
                    recommendation_id=recommendation.id,
                    expected_learning_update_id=recommendation.learning_update_id,
                )
            )
            assert generated.practice is not None
            stale_practice_id = generated.practice.id
            _add_episode(
                session,
                attempt_id=102,
                evaluation_id=202,
                created_at=datetime(2026, 3, 1, tzinfo=UTC),
                band="6.5",
            )
            session.commit()
            apply_writing_evaluation(session, learner_id=1, writing_evaluation_id=202)
            forbidden = _ForbiddenWritingProvider()
            rejected = False
            try:
                asyncio.run(
                    AgentTurnExecutor(
                        tools=AgentTools(
                            session=session, provider_factory=lambda: forbidden
                        ),
                        observe=lambda learner_id: observe_agent_state(
                            session, learner_id=learner_id
                        ),
                    ).execute(
                        learner_id=1,
                        turn=PracticeSubmissionAgentTurn(
                            turn_type="practice_submission",
                            practice_id=stale_practice_id,
                            essay="Stale canonical regression essay.",
                        ),
                    )
                )
            except AgentStalePracticeError:
                rejected = True
            stale_practice = session.get(WritingPractice, stale_practice_id)
            safe = (
                rejected
                and not forbidden.requests
                and stale_practice is not None
                and stale_practice.lifecycle_state
                == PracticeLifecycleState.GENERATED.value
                and stale_practice.attempt_id is None
            )
        observed = {"provider_calls": len(forbidden.requests), "safe_conflict": safe}
        authority = AuthorityEvidence(
            authoritative_operation_succeeded=safe,
            reported_success=safe,
            case_valid=safe,
        )
        return (
            _finding(evaluate_outcome(case, observed)),
            _finding(evaluate_authority(authority)),
        )

    def _unknown_knowledge(self, case: RegressionCase) -> tuple[FindingEvidence, ...]:
        knowledge_id = str(case.input["knowledge_id"])
        raw = evaluate_knowledge_grounding(knowledge_ids=(knowledge_id,))
        normalized = _expected_fail_closed(raw, failure_code="knowledge_unknown_id")
        safe = normalized.status is EvalStatus.PASS
        authority = AuthorityEvidence(
            authoritative_operation_succeeded=safe,
            reported_success=safe,
            knowledge_provenance_known=safe,
            case_valid=safe,
        )
        return (_finding(normalized), _finding(evaluate_authority(authority)))

    def _bounded_agent(self, case: RegressionCase) -> tuple[FindingEvidence, ...]:
        tools = _BoundedAgentTools()
        states = iter(
            (
                _agent_state(ObservationKind.NEEDS_PRACTICE_SUBMISSION),
                _agent_state(ObservationKind.NEEDS_COMPLETION),
                _agent_state(ObservationKind.NEEDS_GENERATION),
                _agent_state(ObservationKind.NEEDS_PRACTICE_SUBMISSION),
            )
        )
        response = asyncio.run(
            AgentTurnExecutor(
                tools=tools, observe=lambda _learner_id: next(states)
            ).execute(
                learner_id=1,
                turn=PracticeSubmissionAgentTurn(
                    turn_type="practice_submission",
                    practice_id=9,
                    essay="Canonical bounded trajectory essay.",
                ),
            )
        )
        mutations = sum(step.tool is not AgentTool.OBSERVE for step in response.steps)
        observations = sum(step.tool is AgentTool.OBSERVE for step in response.steps)
        provider_calls = sum(
            step.outcome
            in {AgentOutcome.PRACTICE_GENERATED, AgentOutcome.SUBMISSION_SUBMITTED}
            for step in response.steps
        )
        observed = {
            "max_mutations": MAX_MUTATING_TOOL_EXECUTIONS,
            "max_observations": MAX_OBSERVATIONS,
            "max_provider_calls": MAX_PROVIDER_BACKED_SERVICE_INVOCATIONS,
            "actual_mutations": mutations,
            "actual_observations": observations,
            "actual_provider_calls": provider_calls,
        }
        return (
            _finding(evaluate_trajectory(response)),
            _finding(evaluate_outcome(case, observed)),
        )

    def _multi_episode(self, case: RegressionCase) -> tuple[FindingEvidence, ...]:
        with self._factory() as session:
            run = self._build_lifecycle(session, include_practice=True)
        observed = {
            "accepted_updates": run.accepted_updates,
            "duplicate_effects": run.duplicate_effects,
            "planner_projection": (
                "authoritative_current_projection"
                if run.planner_projection_valid
                else "invalid"
            ),
        }
        safe = (
            run.accepted_updates == 2
            and run.duplicate_effects == 0
            and run.planner_projection_valid
        )
        authority = AuthorityEvidence(
            authoritative_operation_succeeded=safe,
            reported_success=safe,
            case_valid=safe,
        )
        return (
            _finding(evaluate_outcome(case, observed)),
            _finding(evaluate_lifecycle(run.evidence)),
            _finding(evaluate_authority(authority)),
        )

    def _build_lifecycle(
        self, session: Session, *, include_practice: bool = False
    ) -> _LifecycleRun:
        older = datetime(2026, 1, 1, tzinfo=UTC)
        newer = datetime(2026, 2, 1, tzinfo=UTC)
        session.add(Learner(id=1, writing_target_band=Decimal("7.0")))
        _add_episode(
            session, attempt_id=100, evaluation_id=200, created_at=older, band="6.0"
        )
        _add_episode(
            session, attempt_id=101, evaluation_id=201, created_at=newer, band="7.0"
        )
        session.commit()

        apply_writing_evaluation(session, learner_id=1, writing_evaluation_id=201)
        accepted_older = apply_writing_evaluation(
            session, learner_id=1, writing_evaluation_id=200
        )
        before_replay = _read_counts(session)
        replay = apply_writing_evaluation(
            session, learner_id=1, writing_evaluation_id=200
        )
        after_replay = _read_counts(session)
        duplicate_effects = sum(
            after - before
            for before, after in zip(before_replay, after_replay, strict=True)
        )
        if (
            not replay.reused
            or replay.learning_update_id != accepted_older.learning_update_id
        ):
            duplicate_effects += 1

        updates = tuple(
            session.scalars(
                select(LearningUpdate)
                .where(LearningUpdate.learner_id == 1)
                .order_by(LearningUpdate.id)
            ).all()
        )
        current_update = max(updates, key=lambda row: row.id)
        recommendation = session.scalar(
            select(PracticeRecommendation).where(
                PracticeRecommendation.learning_update_id == current_update.id
            )
        )
        assert recommendation is not None
        states = tuple(
            session.scalars(
                select(LearnerSkillState).where(LearnerSkillState.learner_id == 1)
            ).all()
        )
        task_state = next(state for state in states if state.skill == "task_response")
        assert task_state.last_evidence_id is not None
        last_evidence = session.get(LearningEvidence, task_state.last_evidence_id)
        assert last_evidence is not None
        attempts = tuple(
            session.scalars(
                select(WritingAttempt).where(WritingAttempt.id.in_((100, 101)))
            ).all()
        )
        ordered_attempts = tuple(
            sorted(attempts, key=lambda row: (row.created_at, row.id))
        )
        episodes = list_learner_episodes(session, learner_id=1)
        planner_snapshot = recommendation.planner_context_snapshot or {}
        planner_stages = tuple(
            stage["stage"]
            for stage in planner_snapshot.get("selection_trace", {}).get("stages", ())
        )

        practice = None
        knowledge_ids: tuple[str, ...] = ()
        grounding = None
        if include_practice:
            generator = _DeterministicPracticeGenerator()
            generated = asyncio.run(
                PracticeGenerationService(
                    session, generator
                ).generate_or_resolve_current(
                    learner_id=1,
                    recommendation_id=recommendation.id,
                    expected_learning_update_id=current_update.id,
                )
            )
            assert generated.practice is not None and len(generator.requests) == 1
            practice = generated.practice
            request = generator.requests[0]
            assert request.knowledge_context is not None
            knowledge_ids = tuple(
                item.knowledge_id for item in request.knowledge_context.items
            )
            query = KnowledgeRetrievalQuery(
                purpose=KnowledgeRetrievalPurpose.PRACTICE_GENERATION,
                criterion=recommendation.target_skill,
                current_band=normalize_generation_current_band(
                    Decimal(recommendation.current_estimate)
                ),
                target_band=BandScore(
                    value=Decimal(recommendation.learner_target_band)
                ),
            )
            expected_ids = tuple(
                unit.knowledge_id for unit in retrieve_knowledge(query).units
            )
            if knowledge_ids != expected_ids:
                raise ValueError(
                    "practice knowledge context does not match deterministic retrieval"
                )
            snapshot_by_id = {
                unit.knowledge_id: unit for unit in WRITING_TASK2_KNOWLEDGE_UNITS
            }
            for item in request.knowledge_context.items:
                if item.source_ids != tuple(
                    ref.source_id
                    for ref in snapshot_by_id[item.knowledge_id].source_refs
                ):
                    raise ValueError("practice knowledge source provenance mismatch")
            grounding = GroundingEvidence(
                learner_id=1,
                current_learning_update_id=current_update.id,
                recommendation_learner_id=recommendation.learner_id,
                recommendation_learning_update_id=recommendation.learning_update_id,
                recommendation=GroundedRecommendationSummary(
                    id=recommendation.id,
                    decision_type="practice",
                    target_skill=recommendation.target_skill,
                    learner_target_band=BandScore(
                        value=Decimal(recommendation.learner_target_band)
                    ),
                    current_estimate=Decimal(recommendation.current_estimate),
                    reason_codes=tuple(recommendation.reason_codes),
                ),
                query=query,
                knowledge_ids=knowledge_ids,
                practice_knowledge_source_ids={
                    item.knowledge_id: item.source_ids
                    for item in request.knowledge_context.items
                },
            )

        before_reads = _read_counts(session)
        repeated_episodes = list_learner_episodes(session, learner_id=1)
        after_reads = _read_counts(session)
        observed = observe_agent_state(session, learner_id=1)
        evidence = LifecycleEvidence(
            learner_id=1,
            writing_evaluation_ids=tuple(
                update.writing_evaluation_id for update in updates
            ),
            learning_updates=tuple(
                OrderedLifecycleRecord(id=update.id, created_at=update.created_at)
                for update in updates
            ),
            learning_update_evaluation_ids=tuple(
                update.writing_evaluation_id for update in updates
            ),
            attempts_in_state_order=tuple(
                OrderedLifecycleRecord(id=attempt.id, created_at=attempt.created_at)
                for attempt in ordered_attempts
            ),
            state_last_attempt_id=last_evidence.source_attempt_id,
            memory_update_ids=tuple(episode.episode_id for episode in episodes),
            current_learning_update_id=observed.latest_learning_update_id,
            recommendation_id=recommendation.id,
            recommendation_learner_id=recommendation.learner_id,
            recommendation_learning_update_id=recommendation.learning_update_id,
            practice_id=practice.id if practice else None,
            practice_learner_id=practice.learner_id if practice else None,
            practice_recommendation_id=practice.recommendation_id if practice else None,
            knowledge_ids=knowledge_ids,
            grounding_evidence=grounding,
            replay_duplicate_effects=duplicate_effects,
            read_counts_before=before_reads,
            read_counts_after=after_reads,
        )
        return _LifecycleRun(
            evidence=evidence,
            accepted_updates=len(updates),
            duplicate_effects=duplicate_effects,
            state_chronology_valid=(
                tuple(attempt.id for attempt in ordered_attempts) == (100, 101)
                and last_evidence.source_attempt_id == 101
            ),
            planner_stages=planner_stages,
            planner_projection_valid=(
                recommendation.learning_update_id == current_update.id
                and observed.latest_learning_update_id == current_update.id
                and tuple(episode.episode_id for episode in repeated_episodes)
                == tuple(episode.episode_id for episode in episodes)
            ),
        )


def run_canonical_regression(
    *,
    run_id: str,
    database_url: str,
    fixture_root: Path = CANONICAL_FIXTURE_ROOT,
) -> RunnerSuiteResult:
    """Load and execute the complete official corpus with no injected registry."""

    validated_url = validate_test_database_url(
        database_url, os.getenv("IELTS_DATABASE_URL")
    )
    corpus_path = fixture_root / "regression_corpus.json"
    corpus = load_regression_corpus(corpus_path, fixture_directory=fixture_root)
    command.upgrade(_alembic_config(validated_url), "head")
    engine: Engine = create_engine(validated_url, pool_pre_ping=True)
    try:
        runtime = CanonicalRegressionRuntime(
            factory=create_session_factory(engine),
            fixture_root=fixture_root,
        )
        executors = runtime.executors(corpus)
        return EvalRunner(max_cases=len(corpus.cases)).run_deterministic(
            run_id=run_id,
            corpus=corpus,
            executors=executors,
        )
    finally:
        engine.dispose()


def execute_canonical_regression(
    *,
    run_id: str,
    database_url: str,
    fixture_root: Path = CANONICAL_FIXTURE_ROOT,
) -> CanonicalRegressionExecution:
    """Execute the suite and derive both P10-13 report representations."""

    suite = run_canonical_regression(
        run_id=run_id,
        database_url=database_url,
        fixture_root=fixture_root,
    )
    structured = build_structured_report(suite, config_version=REPORT_CONFIG_VERSION)
    return CanonicalRegressionExecution(
        suite=suite,
        structured_report=structured,
        human_report=render_human_report(structured),
    )


def main() -> int:
    database_url = os.getenv("IELTS_TEST_DATABASE_URL")
    if database_url is None:
        print(
            "IELTS_TEST_DATABASE_URL is required for canonical regression.",
            file=sys.stderr,
        )
        return 2
    os.environ.pop("IELTS_DEEPSEEK_API_KEY", None)
    try:
        execution = execute_canonical_regression(
            run_id="phase10-canonical-regression",
            database_url=database_url,
        )
    except Exception as error:
        print(
            f"Canonical regression infrastructure failure: {type(error).__name__}",
            file=sys.stderr,
        )
        return 2
    print(execution.human_report, end="")
    return 0 if execution.suite.status is EvalStatus.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CANONICAL_CORPUS_PATH",
    "CANONICAL_FIXTURE_ROOT",
    "CanonicalRegistryError",
    "CanonicalRegressionExecution",
    "CanonicalRegressionRuntime",
    "execute_canonical_regression",
    "run_canonical_regression",
    "validate_canonical_executor_registry",
]
