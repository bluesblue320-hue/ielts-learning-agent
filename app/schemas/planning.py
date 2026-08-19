"""P3-08 planner-owned decision contract.

Strict Pydantic v2 schemas for the deterministic practice-planning decision.
These schemas express the accepted P3-08 policy (version
``writing-practice-gap-v1``) and contain no planner algorithm, ORM, transaction,
or LLM behavior. The production planner implementation is owned by P3-09.

The schema validates only local decision invariants: it never recomputes all
skill gaps or re-runs tie-break selection to prove that ``target_skill`` is the
largest-gap skill. That selection algorithm belongs to P3-09.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.learner.planning_policy import MIN_ESTABLISHED_EVIDENCE_COUNT
from app.learner.writing_policy import WRITING_SKILLS
from app.schemas.common import BandScore
from app.schemas.learner import (
    DerivedStateBand,
    LearnerSkillStateSet,
    WritingSkillKey,
)


class DecisionType(StrEnum):
    """The two mutually exclusive planning decision types."""

    PRACTICE = "practice"
    NO_PRACTICE = "no_practice"


class PlannerReasonCode(StrEnum):
    """The frozen planner v1 reason-code taxonomy."""

    LARGEST_TARGET_GAP = "largest_target_gap"
    PRIORITY_TIEBREAK = "priority_tiebreak"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    TARGET_ACHIEVED = "target_achieved"
    COLD_START = "cold_start"
    INCOMPLETE_STATE = "incomplete_state"
    TARGET_UNSET = "target_unset"


PlannerVersion = Literal["writing-practice-gap-v1"]
PlannerV2Version = Literal["writing-practice-gap-memory-v2"]

# These versions deliberately live beside the strict planner decision schemas,
# rather than in a mutable application configuration. A persisted decision is
# a versioned domain fact, not a runtime feature-flag result.
MemoryContextVersion = Literal["writing-memory-aware-planning-context-v1"]
SelectionTraceVersion = Literal["writing-planner-selection-trace-v1"]
PlannerSnapshotVersion = Literal["writing-practice-gap-memory-v2-audit-v1"]

TrendStatus = Literal[
    "improving",
    "stable",
    "declining",
    "insufficient_history",
]
PersistentGapStatus = Literal["established", "insufficient_history"]
PlanningSelectionStage = Literal[
    "persistent_gap",
    "trend",
    "recent_practice",
    "canonical_priority",
]

_CANONICAL_SKILL_ORDER = (
    "task_response",
    "coherence_and_cohesion",
    "lexical_resource",
    "grammatical_range_and_accuracy",
)
_SELECTION_STAGE_ORDER = (
    "persistent_gap",
    "trend",
    "recent_practice",
    "canonical_priority",
)
_PositiveIdentifier = Annotated[int, Field(gt=0)]

# Exact valid reason-code sequences for planner v1. Ordering is fully
# deterministic: any sequence not listed here is rejected, never reordered.
_VALID_PRACTICE_REASON_SEQUENCES = frozenset(
    {
        (PlannerReasonCode.LARGEST_TARGET_GAP,),
        (PlannerReasonCode.LARGEST_TARGET_GAP, PlannerReasonCode.PRIORITY_TIEBREAK),
        (PlannerReasonCode.LARGEST_TARGET_GAP, PlannerReasonCode.INSUFFICIENT_EVIDENCE),
        (
            PlannerReasonCode.LARGEST_TARGET_GAP,
            PlannerReasonCode.PRIORITY_TIEBREAK,
            PlannerReasonCode.INSUFFICIENT_EVIDENCE,
        ),
    }
)

_VALID_NO_PRACTICE_REASON_SEQUENCES = frozenset(
    {
        (PlannerReasonCode.TARGET_ACHIEVED,),
        (PlannerReasonCode.TARGET_ACHIEVED, PlannerReasonCode.INSUFFICIENT_EVIDENCE),
        (PlannerReasonCode.COLD_START,),
        (PlannerReasonCode.INCOMPLETE_STATE,),
        (PlannerReasonCode.TARGET_UNSET,),
    }
)


class PracticeRecommendationDecision(BaseModel):
    """The structured, auditable planner decision for one learning update.

    A valid decision is either ``practice`` with a required ``target_skill`` and
    estimate that matches the state snapshot, or ``no_practice`` with a null
    ``target_skill``. Every decision carries exactly one valid reason-code
    sequence, a full decision-time state snapshot, and the frozen planner
    version. The reason semantics must agree with the state snapshot.
    """

    model_config = ConfigDict(extra="forbid")

    decision_type: DecisionType
    target_skill: WritingSkillKey | None = None
    learner_target_band: BandScore | None = None
    current_estimate: DerivedStateBand | None = None
    reason_codes: list[PlannerReasonCode]
    planner_version: PlannerVersion
    state_snapshot: LearnerSkillStateSet

    @model_validator(mode="after")
    def _check_decision_contract(self) -> "PracticeRecommendationDecision":
        sequence = tuple(self.reason_codes)

        if self.decision_type == DecisionType.PRACTICE:
            self._check_practice(sequence)
        else:
            self._check_no_practice(sequence)
        return self

    def _check_practice(
        self, sequence: tuple[PlannerReasonCode, ...]
    ) -> None:
        if sequence not in _VALID_PRACTICE_REASON_SEQUENCES:
            raise ValueError(
                "invalid practice reason sequence: "
                f"{[code.value for code in self.reason_codes]}"
            )
        if self.target_skill is None:
            raise ValueError("practice decision requires target_skill")
        if self.learner_target_band is None:
            raise ValueError("practice decision requires learner_target_band")
        if self.current_estimate is None:
            raise ValueError("practice decision requires current_estimate")

        snapshot_state = getattr(self.state_snapshot, self.target_skill)
        if snapshot_state.estimated_band is None:
            raise ValueError(
                "practice target skill must be observed in the state snapshot"
            )
        if self.current_estimate != snapshot_state.estimated_band:
            raise ValueError(
                "current_estimate must equal the snapshot estimate for target_skill"
            )
        if self.current_estimate >= self.learner_target_band.value:
            raise ValueError("practice requires a strictly positive target gap")

        # Bidirectional evidence qualifier rule for the selected skill.
        has_insufficient = (
            PlannerReasonCode.INSUFFICIENT_EVIDENCE in self.reason_codes
        )
        low_evidence = snapshot_state.evidence_count < MIN_ESTABLISHED_EVIDENCE_COUNT
        if low_evidence and not has_insufficient:
            raise ValueError(
                "selected skill has low evidence but reason lacks "
                "insufficient_evidence"
            )
        if not low_evidence and has_insufficient:
            raise ValueError(
                "selected skill has established evidence but reason carries "
                "insufficient_evidence"
            )

    def _check_no_practice(
        self, sequence: tuple[PlannerReasonCode, ...]
    ) -> None:
        if sequence not in _VALID_NO_PRACTICE_REASON_SEQUENCES:
            raise ValueError(
                "invalid no_practice reason sequence: "
                f"{[code.value for code in self.reason_codes]}"
            )
        if self.target_skill is not None:
            raise ValueError("no_practice decision must have null target_skill")
        if self.current_estimate is not None:
            raise ValueError("no_practice decision must have null current_estimate")

        primary = self.reason_codes[0]

        if primary == PlannerReasonCode.TARGET_UNSET:
            if self.learner_target_band is not None:
                raise ValueError(
                    "target_unset decision must have null learner_target_band"
                )
            # No snapshot-shape requirement for target_unset.
            return

        if self.learner_target_band is None:
            raise ValueError(
                "no_practice decision (non target_unset) requires learner_target_band"
            )

        states = [getattr(self.state_snapshot, skill) for skill in WRITING_SKILLS]
        observed = [s for s in states if s.estimated_band is not None]

        if primary == PlannerReasonCode.TARGET_ACHIEVED:
            if len(observed) != len(states):
                raise ValueError(
                    "target_achieved requires all four skills observed"
                )
            target = self.learner_target_band.value
            for state in states:
                if state.estimated_band < target:
                    raise ValueError(
                        "target_achieved requires every skill >= target"
                    )
            low = any(
                s.evidence_count < MIN_ESTABLISHED_EVIDENCE_COUNT for s in states
            )
            has_insufficient = (
                PlannerReasonCode.INSUFFICIENT_EVIDENCE in self.reason_codes
            )
            if low and not has_insufficient:
                raise ValueError(
                    "target_achieved requires insufficient_evidence when any "
                    "skill has low evidence"
                )
            if not low and has_insufficient:
                raise ValueError(
                    "target_achieved must not carry insufficient_evidence when "
                    "all skills are established"
                )
        elif primary == PlannerReasonCode.COLD_START:
            if observed:
                raise ValueError("cold_start requires all four skills unobserved")
        elif primary == PlannerReasonCode.INCOMPLETE_STATE:
            if not observed:
                raise ValueError(
                    "incomplete_state requires at least one observed skill"
                )
            if len(observed) == len(states):
                raise ValueError(
                    "incomplete_state requires at least one unobserved skill"
                )

# ---------------------------------------------------------------------------
# Phase 7 — memory-aware planner v2 contracts
# ---------------------------------------------------------------------------


class PracticeRecommendationDecisionV2(PracticeRecommendationDecision):
    """Strict v2 planner decision with the unchanged v1 local semantics.

    The v2 planner changes only how an exact maximum-gap tie is selected. Its
    externally visible decision shape and reason-code taxonomy deliberately
    remain the v1 contract, while the literal planner version keeps historical
    reconstruction unambiguous.
    """

    planner_version: PlannerV2Version


# Keep the pre-Phase-7 model name as the strict v1 contract.  New boundaries
# can use this explicit alias and the discriminated union below without
# widening old callers to accept a v2 planner version.
PracticeRecommendationDecisionV1 = PracticeRecommendationDecision
AnyPracticeRecommendationDecision = Annotated[
    Union[PracticeRecommendationDecisionV1, PracticeRecommendationDecisionV2],
    Field(discriminator="planner_version"),
]


class MemoryAwarePlanningSkillContext(BaseModel):
    """Planner-relevant Memory facts for one canonical Writing skill.

    This is an input fact bundle only. It intentionally contains no selected
    skill, stage result, or selection trace.
    """

    model_config = ConfigDict(extra="forbid")

    skill: WritingSkillKey
    trend: TrendStatus
    persistent_gap: bool
    persistent_gap_status: PersistentGapStatus
    recent_practice_count: int = Field(ge=0)
    source_observation_ids: list[_PositiveIdentifier] = Field(
        default_factory=list,
        max_length=3,
    )
    source_episode_ids: list[_PositiveIdentifier] = Field(
        default_factory=list,
        max_length=3,
    )
    recent_practice_source_episode_ids: list[_PositiveIdentifier] = Field(
        min_length=1,
        max_length=3,
    )

    @model_validator(mode="after")
    def _check_provenance_shape(self) -> "MemoryAwarePlanningSkillContext":
        if len(self.source_observation_ids) != len(self.source_episode_ids):
            raise ValueError(
                "source_observation_ids and source_episode_ids must have equal lengths"
            )
        for field_name in (
            "source_observation_ids",
            "source_episode_ids",
            "recent_practice_source_episode_ids",
        ):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicate ids")
        return self


class MemoryAwarePlanningSkillContextSet(BaseModel):
    """Exactly four canonical planner input fact bundles."""

    model_config = ConfigDict(extra="forbid")

    task_response: MemoryAwarePlanningSkillContext
    coherence_and_cohesion: MemoryAwarePlanningSkillContext
    lexical_resource: MemoryAwarePlanningSkillContext
    grammatical_range_and_accuracy: MemoryAwarePlanningSkillContext

    @model_validator(mode="after")
    def _check_complete_canonical_shape(self) -> "MemoryAwarePlanningSkillContextSet":
        for skill in _CANONICAL_SKILL_ORDER:
            if getattr(self, skill).skill != skill:
                raise ValueError(f"{skill} context must carry matching skill")

        recent_windows = [
            getattr(self, skill).recent_practice_source_episode_ids
            for skill in _CANONICAL_SKILL_ORDER
        ]
        if any(window != recent_windows[0] for window in recent_windows[1:]):
            raise ValueError(
                "recent_practice_source_episode_ids must be the same accepted-update "
                "window for every skill"
            )
        return self


class MemoryAwarePlanningContext(BaseModel):
    """Strict input to a v2 exact-tie resolver, never planner output."""

    model_config = ConfigDict(extra="forbid")

    memory_version: Literal["writing-memory-v1"]
    progress_version: Literal["writing-progress-v1"]
    memory_context_version: MemoryContextVersion
    skills: MemoryAwarePlanningSkillContextSet


def _validate_canonical_skill_list(
    candidates: list[WritingSkillKey],
    *,
    field_name: str,
) -> None:
    if len(candidates) != len(set(candidates)):
        raise ValueError(f"{field_name} must not contain duplicate skills")
    expected = [skill for skill in _CANONICAL_SKILL_ORDER if skill in candidates]
    if candidates != expected:
        raise ValueError(f"{field_name} must use canonical Writing skill order")


class PlannerSelectionTraceStage(BaseModel):
    """One considered v2 exact-tie stage and its normalized candidates."""

    model_config = ConfigDict(extra="forbid")

    stage: PlanningSelectionStage
    candidates_before: list[WritingSkillKey] = Field(min_length=2)
    candidates_after: list[WritingSkillKey] = Field(min_length=1)
    narrowed: bool

    @model_validator(mode="after")
    def _check_stage_contract(self) -> "PlannerSelectionTraceStage":
        _validate_canonical_skill_list(
            self.candidates_before,
            field_name="candidates_before",
        )
        _validate_canonical_skill_list(
            self.candidates_after,
            field_name="candidates_after",
        )
        if not set(self.candidates_after).issubset(self.candidates_before):
            raise ValueError("candidates_after must be a subset of candidates_before")
        narrowed = len(self.candidates_after) < len(self.candidates_before)
        if self.narrowed != narrowed:
            raise ValueError("narrowed must exactly match the candidate-count change")
        if self.stage == "canonical_priority":
            selected = next(
                skill
                for skill in _CANONICAL_SKILL_ORDER
                if skill in self.candidates_before
            )
            if self.candidates_after != [selected]:
                raise ValueError(
                    "canonical_priority must select the first remaining canonical skill"
                )
        return self


class PlannerSelectionTrace(BaseModel):
    """Auditable output of a v2 resolver for an exact maximum-gap tie."""

    model_config = ConfigDict(extra="forbid")

    trace_version: SelectionTraceVersion
    initial_max_gap_candidates: list[WritingSkillKey] = Field(min_length=2)
    stages: list[PlannerSelectionTraceStage] = Field(min_length=1, max_length=4)
    selected_skill: WritingSkillKey

    @model_validator(mode="after")
    def _check_trace_contract(self) -> "PlannerSelectionTrace":
        _validate_canonical_skill_list(
            self.initial_max_gap_candidates,
            field_name="initial_max_gap_candidates",
        )

        expected_stages = list(_SELECTION_STAGE_ORDER[: len(self.stages)])
        actual_stages = [stage.stage for stage in self.stages]
        if actual_stages != expected_stages:
            raise ValueError("selection trace stages must be an ordered policy prefix")

        candidates = self.initial_max_gap_candidates
        for index, stage in enumerate(self.stages):
            if stage.candidates_before != candidates:
                raise ValueError(
                    "each trace stage must start with the preceding candidate set"
                )
            candidates = stage.candidates_after
            if len(candidates) == 1 and index != len(self.stages) - 1:
                raise ValueError("stages after selection must be omitted")

        if len(candidates) != 1:
            raise ValueError("selection trace must resolve to exactly one skill")
        if candidates[0] != self.selected_skill:
            raise ValueError("selected_skill must equal the final trace candidate")

        return self


class PersistedPlannerContextSnapshot(BaseModel):
    """Internal immutable audit envelope for a v2 exact-tie decision."""

    model_config = ConfigDict(extra="forbid")

    snapshot_version: PlannerSnapshotVersion
    memory_context: MemoryAwarePlanningContext
    selection_trace: PlannerSelectionTrace


class PlanningExplanationFactor(StrEnum):
    """Safe semantic factors suitable for a normal product response."""

    EQUAL_MAXIMUM_TARGET_GAP = "equal_maximum_target_gap"
    PERSISTENT_GAP_TIEBREAK = "persistent_gap_tiebreak"
    TREND_TIEBREAK = "trend_tiebreak"
    LOWER_RECENT_PRACTICE_COUNT = "lower_recent_practice_count"
    CANONICAL_PRIORITY_TIEBREAK = "canonical_priority_tiebreak"


class PublicPlanningExplanation(BaseModel):
    """Public v2 explanation derived from a persisted selection trace only."""

    model_config = ConfigDict(extra="forbid")

    factors: list[PlanningExplanationFactor] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def _check_factor_order(self) -> "PublicPlanningExplanation":
        if self.factors[0] != PlanningExplanationFactor.EQUAL_MAXIMUM_TARGET_GAP:
            raise ValueError("a planning explanation starts with equal maximum target gap")
        if len(self.factors) != len(set(self.factors)):
            raise ValueError("planning explanation factors must not repeat")
        return self


class PublicPracticeRecommendationDecisionV2(PracticeRecommendationDecisionV2):
    """Safe v2 product decision, optionally explained from a stored trace.

    This is intentionally distinct from the immutable persisted decision model:
    it contains no audit envelope or provenance ids.
    """

    planning_explanation: PublicPlanningExplanation | None = None


PublicPracticeRecommendationDecision = Annotated[
    Union[PracticeRecommendationDecisionV1, PublicPracticeRecommendationDecisionV2],
    Field(discriminator="planner_version"),
]


class PersistedRecommendationPlanningRecord(BaseModel):
    """Versioned persistence boundary for a decision and its audit envelope.

    The database check remains intentionally shallow (``NULL`` or JSON object).
    This strict domain model owns the conditional semantic matrix instead of
    attempting to encode planner selection logic in PostgreSQL JSONB SQL.
    """

    model_config = ConfigDict(extra="forbid")

    decision: AnyPracticeRecommendationDecision
    planner_context_snapshot: PersistedPlannerContextSnapshot | None = None

    @model_validator(mode="after")
    def _check_snapshot_presence_matrix(
        self,
    ) -> "PersistedRecommendationPlanningRecord":
        decision = self.decision
        snapshot = self.planner_context_snapshot

        if decision.planner_version == "writing-practice-gap-v1":
            if snapshot is not None:
                raise ValueError("v1 recommendations must not carry a planner snapshot")
            return self

        if decision.decision_type == DecisionType.NO_PRACTICE:
            if snapshot is not None:
                raise ValueError("v2 no_practice recommendations must not carry a snapshot")
            return self

        # A v2 practice decision is locally validated to have a target and
        # fully observed state snapshot. Recomputing its four simple state gaps
        # here distinguishes the required exact-tie envelope from a unique gap
        # without re-running the tie resolver or querying persistence.
        assert decision.learner_target_band is not None
        target = decision.learner_target_band.value
        gaps = {
            skill: target - getattr(decision.state_snapshot, skill).estimated_band
            for skill in _CANONICAL_SKILL_ORDER
        }
        maximum = max(gaps.values())
        candidates = [
            skill for skill in _CANONICAL_SKILL_ORDER if gaps[skill] == maximum
        ]
        is_exact_tie = len(candidates) > 1

        if not is_exact_tie:
            if snapshot is not None:
                raise ValueError("v2 unique-gap recommendations must not carry a snapshot")
            return self

        if snapshot is None:
            raise ValueError("v2 exact-tie recommendations require a planner snapshot")
        if snapshot.selection_trace.initial_max_gap_candidates != candidates:
            raise ValueError(
                "selection trace initial candidates must match the decision-time "
                "maximum-gap tie"
            )
        if snapshot.selection_trace.selected_skill != decision.target_skill:
            raise ValueError("selection trace selected_skill must match decision target_skill")
        return self
