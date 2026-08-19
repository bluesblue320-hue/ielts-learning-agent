"""Phase 6 memory domain and API read-contract boundaries (P6-03).

Strict Pydantic v2 read models for the frozen Phase 6 hierarchical learning
memory contract (``writing-memory-v1`` / ``writing-progress-v1``). These are
derived read-model boundaries: L1/L2/L3 are NOT persisted, carry no invented
persistent memory ids (``memory_atom_id`` / ``pattern_id`` / ``profile_id``),
and expose only real authoritative source ids (``learning_update_id``,
``learning_evidence_id``, ``writing_evaluation_id``, ``writing_practice_id``,
``recommendation_id``, ``attempt_id``).

Semantic boundaries enforced at the schema layer:

- L0 episode summaries/details carry the persisted episode anchor id and
  ``occurred_at`` exactly equal to ``LearningUpdate.created_at``;
- the historical ``target_snapshot`` is sourced ONLY from
  ``PracticeRecommendation.learner_target_band``; the current
  ``Learner.writing_target_band`` is exposed separately and is never used as a
  historical fallback;
- the L3 profile reads current state fields from ``LearnerSkillState`` as a
  reference and never duplicates or replaces the authoritative state engine;
- trend / persistent-gap literals and windows match ``writing-progress-v1``.

No ORM, service, route, provider, or LLM behavior lives here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import BandScore
from app.schemas.learner import (
    DerivedStateBand,
    LearnerSkillStateSet,
    LearningEvidence as LearningEvidenceSchema,
    LearningUpdate as LearningUpdateSchema,
    WritingSkillKey,
)
from app.schemas.planning import AnyPracticeRecommendationDecision
from app.schemas.practice import PracticeResponse
from app.schemas.writing import WritingEvaluationResponse

# Frozen progress-policy version for L2/L3 read models.
PROGRESS_POLICY_VERSION: Literal["writing-progress-v1"] = "writing-progress-v1"
MEMORY_VERSION: Literal["writing-memory-v1"] = "writing-memory-v1"


class MemorySchema(BaseModel):
    """Strict immutable base for Phase 6 memory read boundaries."""

    model_config = ConfigDict(extra="forbid")


EpisodeType = Literal["initial_writing", "targeted_practice"]
TrendStatus = Literal[
    "improving",
    "stable",
    "declining",
    "insufficient_history",
]
PersistentGapStatus = Literal["established", "insufficient_history"]
ResumeAction = Literal[
    "initial_writing",
    "no_action",
    "generate_practice",
    "submit_practice",
    "await_submission",
    "complete_practice",
]


# ---------------------------------------------------------------------------
# L0 — Learning Episode
# ---------------------------------------------------------------------------


class EpisodeSkillObservation(MemorySchema):
    """One canonical skill observation inside an L0 episode.

    ``learning_evidence_id`` is the persisted ``LearningEvidence.id`` that owns
    this observation; ``source_created_at`` / ``source_attempt_id`` are the
    immutable canonical-order values copied from the source attempt.
    """

    skill: WritingSkillKey
    observed_band: BandScore
    learning_evidence_id: int = Field(gt=0)
    source_attempt_id: int = Field(gt=0)
    source_created_at: datetime


class EpisodeSkillObservationSet(MemorySchema):
    """Exactly four canonical skill observations for one episode."""

    task_response: EpisodeSkillObservation
    coherence_and_cohesion: EpisodeSkillObservation
    lexical_resource: EpisodeSkillObservation
    grammatical_range_and_accuracy: EpisodeSkillObservation


class LearningEpisodeSummary(MemorySchema):
    """One learner-owned L0 episode as returned by history.

    ``episode_id`` IS the persisted ``LearningUpdate.id`` (the L0 episode
    anchor). ``occurred_at`` is defined exactly as ``LearningUpdate.created_at``.

    ``practice_target_skill`` is derived from the linked
    ``WritingPractice.target_skill`` (the practice just completed); it is
    ``None`` for ``initial_writing`` episodes. ``recommendation_target_skill``
    remains the NEXT planner recommendation's target and may differ from the
    completed practice's target; the two are never conflated.
    """

    episode_id: int = Field(gt=0)
    episode_type: EpisodeType
    occurred_at: datetime
    writing_evaluation_id: int = Field(gt=0)
    attempt_id: int = Field(gt=0)
    writing_practice_id: int | None = Field(default=None, gt=0)
    practice_target_skill: WritingSkillKey | None = None
    recommendation_id: int = Field(gt=0)
    recommendation_decision_type: Literal["practice", "no_practice"]
    recommendation_target_skill: WritingSkillKey | None = None
    recommendation_reason_codes: list[str] = Field(default_factory=list)
    planner_version: str = Field(min_length=1)
    skill_observations: EpisodeSkillObservationSet


class WritingAttemptView(MemorySchema):
    """The persisted attempt behind an episode (full provenance)."""

    attempt_id: int = Field(gt=0)
    question: str = Field(min_length=1)
    essay: str = Field(min_length=1)
    word_count: int = Field(gt=0)
    created_at: datetime


class LearningEpisodeDetail(MemorySchema):
    """Full L0 reconstruction for one episode.

    ``episode`` is the same summary shape used by history; ``evidence`` is the
    four persisted ``LearningEvidence`` rows; ``recommendation`` is the full
    persisted planner decision; ``practice`` is the linked practice when the
    episode is ``targeted_practice`` (at most one).
    """

    episode: LearningEpisodeSummary
    learning_update: LearningUpdateSchema
    attempt: WritingAttemptView
    evaluation: WritingEvaluationResponse
    evidence: list[LearningEvidenceSchema] = Field(min_length=4, max_length=4)
    recommendation: AnyPracticeRecommendationDecision
    practice: PracticeResponse | None = None


class WritingHistoryResponse(MemorySchema):
    """``GET /learners/{learner_id}/writing/history`` — what did I do?"""

    learner_id: int = Field(gt=0)
    episodes: list[LearningEpisodeSummary] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# L1 — Learning Atom (read-model representations)
# ---------------------------------------------------------------------------


class SkillObservationAtom(MemorySchema):
    """``skill_observation`` — authoritative source is one ``LearningEvidence``."""

    atom_kind: Literal["skill_observation"] = "skill_observation"
    skill: WritingSkillKey
    observed_band: BandScore
    learning_evidence_id: int = Field(gt=0)
    learning_update_id: int = Field(gt=0)
    writing_evaluation_id: int = Field(gt=0)
    source_attempt_id: int = Field(gt=0)
    source_created_at: datetime


class PracticeCompletedAtom(MemorySchema):
    """``practice_completed`` — submitted + linked evaluation applied.

    ``completed_at`` is the applied ``LearningUpdate.created_at``; there is no
    fallback to ``WritingPractice.updated_at``.
    """

    atom_kind: Literal["practice_completed"] = "practice_completed"
    skill: WritingSkillKey
    writing_practice_id: int = Field(gt=0)
    learning_update_id: int = Field(gt=0)
    writing_evaluation_id: int = Field(gt=0)
    attempt_id: int = Field(gt=0)
    completed_at: datetime


class TargetSnapshotAtom(MemorySchema):
    """``target_snapshot`` — the HISTORICAL episode target.

    Sourced ONLY from ``PracticeRecommendation.learner_target_band``; the
    current ``Learner.writing_target_band`` must never be substituted here.
    """

    atom_kind: Literal["target_snapshot"] = "target_snapshot"
    learning_update_id: int = Field(gt=0)
    recommendation_id: int = Field(gt=0)
    historical_target_band: BandScore


class RecommendationObservationAtom(MemorySchema):
    """``recommendation_observation`` — the full persisted planner decision."""

    atom_kind: Literal["recommendation_observation"] = "recommendation_observation"
    learning_update_id: int = Field(gt=0)
    recommendation_id: int = Field(gt=0)
    decision: AnyPracticeRecommendationDecision


# ---------------------------------------------------------------------------
# L2 — Learning Pattern (per-skill longitudinal summary)
# ---------------------------------------------------------------------------


class SkillProgress(MemorySchema):
    """Per-skill L2 pattern plus the per-skill L3 summary fields.

    Identified structurally by ``learner_id + skill + pattern kind +
    policy_version``; no synthetic ``pattern_id``. ``current_estimate`` is read
    from the authoritative ``LearnerSkillState`` (never recomputed here).

    Provenance fields are exact and non-overlapping:

    - ``source_observation_ids``: the ``LearningEvidence.id`` values of the
      latest canonical trend window that produced ``trend``/``persistent_gap``;
    - ``source_episode_ids``: the ``LearningUpdate.id`` values OWNING those
      same trend-window evidence rows (exact L0 drill-down, independent of
      apply chronology);
    - ``recent_practice_source_episode_ids``: the latest
      ``RECENT_PRACTICE_EPISODE_WINDOW`` episode ids used for
      ``recent_practice_count`` — a separate provenance meaning, never merged
      into ``source_episode_ids``.
    """

    learner_id: int = Field(gt=0)
    skill: WritingSkillKey
    policy_version: Literal["writing-progress-v1"]
    current_estimate: DerivedStateBand | None = None
    evidence_count: int = Field(ge=0)
    trend: TrendStatus
    persistent_gap: bool
    persistent_gap_status: PersistentGapStatus
    recent_observation_count: int = Field(ge=0)
    recent_practice_count: int = Field(ge=0)
    latest_observation_time: datetime | None = None
    last_episode_id: int | None = Field(default=None, gt=0)
    source_observation_ids: list[int] = Field(default_factory=list)
    source_episode_ids: list[int] = Field(default_factory=list)
    recent_practice_source_episode_ids: list[int] = Field(default_factory=list)


class SkillProgressSet(MemorySchema):
    """Exactly four per-skill L2 patterns in canonical skill order."""

    task_response: SkillProgress
    coherence_and_cohesion: SkillProgress
    lexical_resource: SkillProgress
    grammatical_range_and_accuracy: SkillProgress


# ---------------------------------------------------------------------------
# L3 — Learner Learning Profile + public read responses
# ---------------------------------------------------------------------------


class WritingProgressResponse(MemorySchema):
    """``GET /learners/{learner_id}/writing/progress`` — how have I changed?

    Includes the L2 per-skill patterns and the L3 profile section: current
    target (``current_writing_target_band``, from ``Learner``), the current
    four-skill state reference (``current_state``, from ``LearnerSkillState``),
    and the per-skill longitudinal summaries.
    """

    learner_id: int = Field(gt=0)
    current_writing_target_band: BandScore
    current_state: LearnerSkillStateSet
    skills: SkillProgressSet
    memory_version: Literal["writing-memory-v1"]
    progress_version: Literal["writing-progress-v1"]


class WritingContextResponse(MemorySchema):
    """``GET /learners/{learner_id}/writing/context`` — where should I continue?

    Server-authoritative resume context for a KNOWN learner id. The resume
    action is deterministic and derived entirely from persisted learner-owned
    data; the endpoint never generates a practice. The unapplied initial
    evaluation resume limitation is accepted: with no learner-owned
    ``LearningUpdate``, ``resume_action`` is ``initial_writing``.
    """

    learner_id: int = Field(gt=0)
    resume_action: ResumeAction
    has_learner_owned_episodes: bool
    latest_learning_update_id: int | None = Field(default=None, gt=0)
    current_recommendation_id: int | None = Field(default=None, gt=0)
    current_recommendation: AnyPracticeRecommendationDecision | None = None
    relevant_practice: PracticeResponse | None = None
    current_state: LearnerSkillStateSet
