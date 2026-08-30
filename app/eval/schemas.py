"""Strict, versioned internal contracts for the Phase 10 Eval Harness.

These models are intentionally internal and provider-free.  They describe
evaluation evidence; they never own Writing scoring, learner state, planning,
Knowledge, or Agent behavior.
"""

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

from app.schemas.common import BandScore
from app.schemas.writing import (
    CriterionBandScores,
    WritingEssayText,
    WritingQuestionText,
)


POLICY_VERSION: Final = "writing-eval-calibration-v1"
REGRESSION_CORPUS_VERSION: Final = "writing-eval-regression-corpus-v1"
CALIBRATION_CORPUS_VERSION: Final = "writing-score-calibration-corpus-v1"
REGRESSION_CASE_SCHEMA_VERSION: Final = "writing-eval-regression-case-v1"
CALIBRATION_CASE_SCHEMA_VERSION: Final = "writing-score-calibration-case-v1"
REFERENCE_LABEL_SCHEMA_VERSION: Final = "writing-score-reference-label-v1"
PROVIDER_CAPTURE_SCHEMA_VERSION: Final = "writing-score-provider-capture-v1"
EVAL_RESULT_SCHEMA_VERSION: Final = "writing-eval-result-v1"
CALIBRATION_RESULT_SCHEMA_VERSION: Final = "writing-score-calibration-result-v1"
FAILURE_TAXONOMY_VERSION: Final = "writing-eval-failure-taxonomy-v1"
REPORT_VERSION: Final = "writing-eval-report-v1"

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
CaseId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")]
JsonObject = dict[str, JsonValue]


class EvalSchema(BaseModel):
    """Frozen strict base for repository-internal Eval artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class EvalMode(StrEnum):
    DETERMINISTIC_REGRESSION = "deterministic_regression"
    LIVE_CALIBRATION = "live_calibration"
    CALIBRATION_REPLAY = "calibration_replay"


class EvalStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    BLOCKED = "blocked"
    INVALID_CASE = "invalid_case"


class EvalSeverity(StrEnum):
    VETO = "veto"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


class FailureBoundary(StrEnum):
    CASE_VALIDATION = "case_validation"
    PROVIDER_CONTRACT = "provider_contract"
    EVALUATION = "evaluation"
    PERSISTENCE = "persistence"
    LEARNING_UPDATE = "learning_update"
    STATE = "state"
    MEMORY = "memory"
    PLANNER = "planner"
    RECOMMENDATION = "recommendation"
    KNOWLEDGE = "knowledge"
    PRACTICE_GENERATION = "practice_generation"
    PRACTICE_SUBMISSION = "practice_submission"
    PRACTICE_COMPLETION = "practice_completion"
    AGENT_TRAJECTORY = "agent_trajectory"
    AUTHORITY = "authority"
    CALIBRATION = "calibration"
    REPORTING = "reporting"
    INFRASTRUCTURE = "infrastructure"


class EvalCategory(StrEnum):
    PROVIDER_CONTRACT = "provider_contract"
    EVALUATION = "evaluation"
    PERSISTENCE = "persistence"
    STATE = "state"
    MEMORY = "memory"
    PLANNER = "planner"
    RECOMMENDATION = "recommendation"
    KNOWLEDGE = "knowledge"
    PRACTICE = "practice"
    AGENT_TRAJECTORY = "agent_trajectory"
    AUTHORITY = "authority"
    LIFECYCLE = "lifecycle"


class EvaluatorId(StrEnum):
    OUTCOME = "outcome"
    TRAJECTORY = "trajectory"
    KNOWLEDGE_GROUNDING = "knowledge_grounding"
    AUTHORITY = "authority"
    LIFECYCLE = "lifecycle"
    WIKI_KNOWLEDGE = "wiki_knowledge"


class ReferenceTier(StrEnum):
    A = "a"
    B = "b"
    C = "c"


class AmbiguityState(StrEnum):
    UNAMBIGUOUS = "unambiguous"
    RATER_DISAGREEMENT = "rater_disagreement"
    INSUFFICIENT_REFERENCE = "insufficient_reference"
    ADJUDICATION_PENDING = "adjudication_pending"
    EXCLUDED_FROM_PRIMARY_METRIC = "excluded_from_primary_metric"


class ProvenanceReference(EvalSchema):
    """Stable, reviewable evidence source and locator."""

    source: NonBlank
    locator: NonBlank
    description: NonBlank | None = None


class EvidenceReference(EvalSchema):
    """Reference to case-owned or persisted application evidence."""

    kind: NonBlank
    locator: NonBlank


class LifecycleEpisodeExpectation(EvalSchema):
    """Stable evidence for one accepted durable Writing learning episode."""

    episode_id: CaseId
    learner_id: NonBlank
    writing_evaluation: EvidenceReference
    learning_update: EvidenceReference
    state_projection: EvidenceReference
    memory_projection: EvidenceReference
    recommendation: EvidenceReference
    replay_duplicate_effects: Literal[0] = 0


class MultiEpisodeLifecycleExpectation(EvalSchema):
    """Required structured evidence for a canonical lifecycle regression case."""

    state_chronology: Literal["writing_attempt_created_at_id_asc"]
    memory_chronology: Literal["learning_update_created_at_id_desc"]
    current_observation_chronology: Literal["learning_update_id_desc"]
    planner_projection: Literal["authoritative_current_projection"]
    episodes: tuple[LifecycleEpisodeExpectation, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def episodes_are_distinct_for_one_learner(self) -> "MultiEpisodeLifecycleExpectation":
        episode_ids = [episode.episode_id for episode in self.episodes]
        learner_ids = {episode.learner_id for episode in self.episodes}
        if len(episode_ids) != len(set(episode_ids)):
            raise ValueError("Multi-episode lifecycle evidence contains duplicate episode IDs.")
        if len(learner_ids) != 1:
            raise ValueError("Multi-episode lifecycle evidence must belong to one learner.")
        return self

class SeverityExpectation(EvalSchema):
    boundary: FailureBoundary
    severity: EvalSeverity


class RegressionCase(EvalSchema):
    """Provider-free deterministic regression-case contract."""

    case_id: CaseId
    schema_version: Literal["writing-eval-regression-case-v1"] = (
        REGRESSION_CASE_SCHEMA_VERSION
    )
    corpus_version: Literal["writing-eval-regression-corpus-v1"] = (
        REGRESSION_CORPUS_VERSION
    )
    description: NonBlank
    category: EvalCategory
    mode: Literal[EvalMode.DETERMINISTIC_REGRESSION] = (
        EvalMode.DETERMINISTIC_REGRESSION
    )
    input: JsonObject
    provider_fixture: NonBlank | None = None
    captured_fixture_reference: NonBlank | None = None
    expected_structured_outcomes: JsonObject
    expected_lifecycle_evidence: tuple[EvidenceReference, ...] = ()
    multi_episode_lifecycle: MultiEpisodeLifecycleExpectation | None = None
    expected_trajectory_constraints: JsonObject = Field(default_factory=dict)
    applicable_evaluators: tuple[EvaluatorId, ...] = Field(min_length=1)
    severity_expectations: tuple[SeverityExpectation, ...] = Field(min_length=1)
    provenance: ProvenanceReference | None = None

    @model_validator(mode="after")
    def fixture_references_are_distinct(self) -> "RegressionCase":
        if self.provider_fixture and self.captured_fixture_reference:
            raise ValueError(
                "A regression case may use a provider fixture or a captured fixture, not both."
            )
        if self.multi_episode_lifecycle is not None and EvaluatorId.LIFECYCLE not in self.applicable_evaluators:
            raise ValueError("Multi-episode lifecycle evidence requires the lifecycle evaluator.")
        return self


class RawReferenceRating(EvalSchema):
    """One preserved independent human/reference rating; never overwritten."""

    schema_version: Literal["writing-score-reference-label-v1"] = (
        REFERENCE_LABEL_SCHEMA_VERSION
    )
    rater_id: NonBlank
    criteria: CriterionBandScores
    overall_band: BandScore | None = None
    provenance: ProvenanceReference
    rating_version: NonBlank | None = None
    rated_at: datetime | None = None


class AdjudicatedReferenceLabel(EvalSchema):
    """Separate resolution of disagreement; raw labels remain intact."""

    schema_version: Literal["writing-score-reference-label-v1"] = (
        REFERENCE_LABEL_SCHEMA_VERSION
    )

    criteria: CriterionBandScores
    overall_band: BandScore | None = None
    provenance: ProvenanceReference
    adjudicated_at: datetime | None = None


class ProviderCapture(EvalSchema):
    """Immutable, secret-free input for Calibration Replay Mode."""

    capture_id: CaseId
    case_id: CaseId
    schema_version: Literal["writing-score-provider-capture-v1"] = (
        PROVIDER_CAPTURE_SCHEMA_VERSION
    )
    provider: NonBlank
    model: NonBlank
    thinking_mode: Literal["enabled", "disabled"]
    prompt_version: NonBlank
    rubric_version: NonBlank
    scoring_policy_version: NonBlank
    provider_structured_payload: JsonObject
    application_normalized_result: JsonObject
    capture_timestamp: datetime
    run_config_version: NonBlank

    @model_validator(mode="after")
    def rejects_private_or_secret_fields(self) -> "ProviderCapture":
        forbidden = {"api_key", "apikey", "secret", "chain_of_thought", "reasoning"}

        def walk(value: JsonValue, path: str = "") -> None:
            if isinstance(value, Mapping):
                for key, nested in value.items():
                    normalized = key.lower().replace("-", "_")
                    if normalized in forbidden:
                        raise ValueError(f"Provider capture contains forbidden field: {path}{key}")
                    walk(nested, f"{path}{key}.")
            elif isinstance(value, list):
                for nested in value:
                    walk(nested, path)

        walk(self.provider_structured_payload)
        walk(self.application_normalized_result)
        return self


class CalibrationCase(EvalSchema):
    """Reference-evidence case for live calibration and replay, never regression truth."""

    case_id: CaseId
    schema_version: Literal["writing-score-calibration-case-v1"] = (
        CALIBRATION_CASE_SCHEMA_VERSION
    )
    corpus_version: Literal["writing-score-calibration-corpus-v1"] = (
        CALIBRATION_CORPUS_VERSION
    )
    question: WritingQuestionText
    essay: WritingEssayText
    reference_labels: tuple[RawReferenceRating, ...] = Field(min_length=1)
    reference_tier: ReferenceTier
    provenance: ProvenanceReference
    ambiguity: AmbiguityState
    adjudication: AdjudicatedReferenceLabel | None = None
    provider_capture_references: tuple[CaseId, ...] = ()

    @model_validator(mode="after")
    def raw_rater_ids_are_unique(self) -> "CalibrationCase":
        ids = [label.rater_id for label in self.reference_labels]
        if len(ids) != len(set(ids)):
            raise ValueError("Calibration case contains duplicate raw rater IDs.")
        return self


class EvalFinding(EvalSchema):
    evaluator: EvaluatorId
    status: EvalStatus
    severity: EvalSeverity
    first_failing_boundary: FailureBoundary | None = None
    failure_codes: tuple[NonBlank, ...] = ()
    evidence_references: tuple[EvidenceReference, ...] = ()

    @model_validator(mode="after")
    def failure_attribution_matches_status(self) -> "EvalFinding":
        if self.status == EvalStatus.FAIL and self.first_failing_boundary is None:
            raise ValueError("A failing finding requires its first failing boundary.")
        if self.status != EvalStatus.FAIL and self.first_failing_boundary is not None:
            raise ValueError("Only a failing finding may identify a failing boundary.")
        return self


class EvalResult(EvalSchema):
    """Versioned structured result boundary; report formatting is owned later."""

    run_id: CaseId
    case_id: CaseId
    schema_version: Literal["writing-eval-result-v1"] = EVAL_RESULT_SCHEMA_VERSION
    mode: EvalMode
    findings: tuple[EvalFinding, ...] = Field(min_length=1)

    @property
    def status(self) -> EvalStatus:
        if any(finding.status == EvalStatus.INVALID_CASE for finding in self.findings):
            return EvalStatus.INVALID_CASE
        if any(finding.status == EvalStatus.BLOCKED for finding in self.findings):
            return EvalStatus.BLOCKED
        if any(finding.status == EvalStatus.FAIL for finding in self.findings):
            return EvalStatus.FAIL
        if all(finding.status == EvalStatus.NOT_APPLICABLE for finding in self.findings):
            return EvalStatus.NOT_APPLICABLE
        return EvalStatus.PASS

    @property
    def severity(self) -> EvalSeverity:
        ordered = (EvalSeverity.VETO, EvalSeverity.MAJOR, EvalSeverity.MINOR, EvalSeverity.INFO)
        return next(
            severity
            for severity in ordered
            if any(finding.severity == severity for finding in self.findings)
        )


class CalibrationResult(EvalSchema):
    """Versioned replay/live calibration result boundary; metrics come in P10-10."""

    run_id: CaseId
    case_id: CaseId
    schema_version: Literal["writing-score-calibration-result-v1"] = (
        CALIBRATION_RESULT_SCHEMA_VERSION
    )
    mode: Literal[EvalMode.LIVE_CALIBRATION, EvalMode.CALIBRATION_REPLAY]
    reference_tier: ReferenceTier
    ambiguity: AmbiguityState
    provider_capture_id: CaseId | None = None


__all__ = [
    "AmbiguityState",
    "CALIBRATION_CASE_SCHEMA_VERSION",
    "CALIBRATION_CORPUS_VERSION",
    "CALIBRATION_RESULT_SCHEMA_VERSION",
    "EVAL_RESULT_SCHEMA_VERSION",
    "FAILURE_TAXONOMY_VERSION",
    "POLICY_VERSION",
    "PROVIDER_CAPTURE_SCHEMA_VERSION",
    "REFERENCE_LABEL_SCHEMA_VERSION",
    "REGRESSION_CASE_SCHEMA_VERSION",
    "REGRESSION_CORPUS_VERSION",
    "REPORT_VERSION",
    "AdjudicatedReferenceLabel",
    "CalibrationCase",
    "CalibrationResult",
    "EvalCategory",
    "EvalFinding",
    "EvalMode",
    "EvalResult",
    "EvalSeverity",
    "EvalStatus",
    "EvaluatorId",
    "EvidenceReference",
    "FailureBoundary",
    "LifecycleEpisodeExpectation",
    "MultiEpisodeLifecycleExpectation",
    "ProviderCapture",
    "ProvenanceReference",
    "RawReferenceRating",
    "ReferenceTier",
    "RegressionCase",
    "SeverityExpectation",
]
