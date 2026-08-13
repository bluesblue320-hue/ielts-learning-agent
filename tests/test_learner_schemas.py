"""P3-03 boundary tests for learner, evidence, and state schemas.

These tests encode the accepted P3-03 schema decisions: strict boundaries,
half-band evidence/target validation, non-half-band derived-state precision,
canonical-skill-only keys, positive identifiers, frozen evidence, safe
defaults, complete four-skill shapes, and safe serialization. They exercise no
ORM, transaction, updater, planner, or LLM behavior.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import get_args

import pytest
from pydantic import ValidationError

from app.learner import writing_policy as policy
from app.schemas.learner import (
    DerivedStateBand,
    Learner,
    LearnerCreate,
    LearnerSkillState,
    LearnerSkillStateSet,
    LearningEvidence,
    LearningEvidenceSet,
    LearningUpdate,
    SkillTaxonomyVersion,
    StatePolicyVersion,
    WritingSkillKey,
)

ALL_FOUR = (
    "task_response",
    "coherence_and_cohesion",
    "lexical_resource",
    "grammatical_range_and_accuracy",
)


def _dt() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0)


def band(value: str | Decimal) -> dict[str, Decimal]:
    return {"value": Decimal(value)}


def provenance_payload() -> dict[str, str]:
    return {
        "provider": "test-provider",
        "model": "test-model",
        "prompt_version": "writing-v2",
        "rubric_version": "writing-task2-v1",
        "scoring_policy_version": "writing-product-band-v1",
        "thinking_mode": "disabled",
    }


def make_evidence(skill: str, observed: str = "6.5", **overrides: object) -> LearningEvidence:
    payload: dict[str, object] = {
        "id": 1,
        "learning_update_id": 1,
        "learner_id": 1,
        "writing_evaluation_id": 1,
        "skill": skill,
        "observed_band": band(observed),
        "source_created_at": _dt(),
        "source_attempt_id": 1,
        "provenance": provenance_payload(),
        "created_at": _dt(),
    }
    payload.update(overrides)
    return LearningEvidence.model_validate(payload)


def make_state(skill: str, estimated: str | None = "6.56", **overrides: object) -> LearnerSkillState:
    payload: dict[str, object] = {
        "learner_id": 1,
        "skill": skill,
        "estimated_band": Decimal(estimated) if estimated is not None else None,
        "evidence_count": 1,
        "last_evidence_id": 1,
        "state_policy_version": "writing-state-ewma-v1",
        "revision": 1,
        "updated_at": _dt(),
    }
    payload.update(overrides)
    return LearnerSkillState.model_validate(payload)


def make_evidence_set() -> LearningEvidenceSet:
    return LearningEvidenceSet.model_validate(
        {skill: make_evidence(skill).model_dump() for skill in ALL_FOUR}
    )


# ---------------------------------------------------------------------------
# Taxonomy / policy-version consistency
# ---------------------------------------------------------------------------


def test_skill_key_matches_frozen_taxonomy() -> None:
    assert set(get_args(WritingSkillKey)) == set(policy.WRITING_SKILLS)


def test_version_literals_match_frozen_policy() -> None:
    assert get_args(SkillTaxonomyVersion) == (policy.WRITING_SKILL_TAXONOMY_VERSION,)
    assert get_args(StatePolicyVersion) == (policy.WRITING_STATE_POLICY_VERSION,)


# ---------------------------------------------------------------------------
# Canonical skills only
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("skill", ALL_FOUR)
def test_all_four_canonical_skills_are_accepted(skill: str) -> None:
    assert make_evidence(skill).skill == skill


@pytest.mark.parametrize("skill", ["grammar", "vocab", "cohesion", "", "task response"])
def test_unknown_skill_is_rejected(skill: str) -> None:
    with pytest.raises(ValidationError):
        make_evidence(skill)


# ---------------------------------------------------------------------------
# Half-band evidence and target
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["0", "0.5", "6.5", "8.5", "9"])
def test_observed_band_accepts_ielts_half_bands(value: str) -> None:
    assert make_evidence("task_response", observed=value).observed_band.value == Decimal(value)


@pytest.mark.parametrize("value", ["5.3", "5.25", "9.5", "-0.5"])
def test_observed_band_rejects_non_half_band_values(value: str) -> None:
    with pytest.raises(ValidationError):
        make_evidence("task_response", observed=value)


def test_writing_target_uses_half_band_semantics() -> None:
    assert LearnerCreate(writing_target_band=band("6.5")).writing_target_band.value == Decimal("6.5")

    for value in ("5.3", "9.5", "5.25"):
        with pytest.raises(ValidationError):
            LearnerCreate(writing_target_band=band(value))


# ---------------------------------------------------------------------------
# Derived state precision (not forced to half-band)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["0.00", "6.00", "6.56", "6.63", "9.00"])
def test_derived_state_accepts_two_decimal_values(value: str) -> None:
    assert make_state("task_response", estimated=value).estimated_band == Decimal(value)


@pytest.mark.parametrize("value", ["6.5", "6.0", "0", "9"])
def test_derived_state_accepts_coarser_values_quantizable_to_two_decimals(value: str) -> None:
    # Coarser values are still multiples of 0.01, so they remain valid.
    assert make_state("task_response", estimated=value).estimated_band == Decimal(value)


@pytest.mark.parametrize("value", ["6.563", "6.5634", "6.561", "9.01", "-0.01"])
def test_derived_state_rejects_out_of_precision_or_range(value: str) -> None:
    with pytest.raises(ValidationError):
        make_state("task_response", estimated=value)


def test_derived_state_is_not_forced_to_half_band() -> None:
    state = make_state("task_response", estimated="6.56")
    assert state.estimated_band is not None
    assert state.estimated_band % Decimal("0.5") != 0


def test_derived_state_type_is_distinct_from_band_score() -> None:
    # The derived value is a bare Decimal, not the half-band BandScore wrapper.
    assert DerivedStateBand is not None
    state = make_state("task_response", estimated="6.56")
    assert isinstance(state.estimated_band, Decimal)


# ---------------------------------------------------------------------------
# Positive identifiers / counts / revisions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    ["id", "learning_update_id", "learner_id", "writing_evaluation_id", "source_attempt_id"],
)
def test_evidence_identifiers_must_be_positive(field: str) -> None:
    with pytest.raises(ValidationError):
        make_evidence("task_response", **{field: 0})


@pytest.mark.parametrize("field", ["id", "learner_id", "writing_evaluation_id"])
def test_update_identifiers_must_be_positive(field: str) -> None:
    payload = {
        "id": 1,
        "learner_id": 1,
        "writing_evaluation_id": 1,
        "skill_taxonomy_version": "writing-core-v1",
        "state_policy_version": "writing-state-ewma-v1",
        "planner_version": "planner-v1",
        "created_at": _dt(),
    }
    payload[field] = 0
    with pytest.raises(ValidationError):
        LearningUpdate.model_validate(payload)


def test_learner_id_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Learner(
            id=0,
            writing_target_band=band("6.5"),
            created_at=_dt(),
            updated_at=_dt(),
        )


def test_counts_and_revision_are_nonnegative() -> None:
    with pytest.raises(ValidationError):
        make_state("task_response", evidence_count=-1)
    with pytest.raises(ValidationError):
        make_state("task_response", revision=-1)


def test_last_evidence_id_must_be_positive_when_present() -> None:
    with pytest.raises(ValidationError):
        make_state("task_response", last_evidence_id=0)


# ---------------------------------------------------------------------------
# UNOBSERVED vs observed consistency
# ---------------------------------------------------------------------------


def test_unobserved_state_requires_no_estimate_no_last_no_revision() -> None:
    state = make_state(
        "task_response",
        estimated=None,
        evidence_count=0,
        last_evidence_id=None,
        revision=0,
    )
    assert state.estimated_band is None
    assert state.last_evidence_id is None
    assert state.evidence_count == 0
    assert state.revision == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"estimated": "6.50"},
        {"last_evidence_id": 1},
        {"revision": 1},
    ],
)
def test_unobserved_state_rejects_inconsistent_fields(overrides: dict[str, object]) -> None:
    base = {
        "estimated": None,
        "evidence_count": 0,
        "last_evidence_id": None,
        "revision": 0,
    }
    with pytest.raises(ValidationError):
        make_state("task_response", **{**base, **overrides})


def test_observed_state_requires_estimate_and_last_evidence() -> None:
    with pytest.raises(ValidationError):
        make_state("task_response", estimated=None, evidence_count=1, last_evidence_id=1, revision=1)
    with pytest.raises(ValidationError):
        make_state("task_response", estimated="6.56", evidence_count=1, last_evidence_id=None, revision=1)
    with pytest.raises(ValidationError):
        make_state("task_response", estimated="6.56", evidence_count=1, last_evidence_id=1, revision=0)


# ---------------------------------------------------------------------------
# Frozen evidence (immutable after acceptance)
# ---------------------------------------------------------------------------


def test_evidence_is_frozen_after_acceptance() -> None:
    evidence = make_evidence("task_response")
    with pytest.raises(ValidationError, match="frozen"):
        evidence.id = 999
    with pytest.raises(ValidationError, match="frozen"):
        evidence.observed_band = band("7.0")


# ---------------------------------------------------------------------------
# Mutable-default safety
# ---------------------------------------------------------------------------


def test_no_shared_mutable_defaults() -> None:
    from pydantic.fields import FieldInfo

    for model in (
        LearnerCreate,
        Learner,
        LearningUpdate,
        LearningEvidence,
        LearnerSkillState,
        LearningEvidenceSet,
        LearnerSkillStateSet,
    ):
        for field_info in model.model_fields.values():
            default = field_info.default
            assert not isinstance(default, (list, dict, set)), (
                f"{model.__name__}.{field_info.alias} uses a mutable default"
            )


def test_evidence_set_instances_do_not_share_state() -> None:
    first = make_evidence_set()
    second = make_evidence_set()
    assert first is not second
    assert first.task_response is not second.task_response


# ---------------------------------------------------------------------------
# Complete four-skill shapes
# ---------------------------------------------------------------------------


def test_evidence_set_accepts_exactly_four_skills() -> None:
    result = make_evidence_set()
    assert result.task_response.skill == "task_response"
    assert result.coherence_and_cohesion.skill == "coherence_and_cohesion"
    assert result.lexical_resource.skill == "lexical_resource"
    assert result.grammatical_range_and_accuracy.skill == "grammatical_range_and_accuracy"


def test_evidence_set_rejects_missing_skill() -> None:
    payload = {skill: make_evidence(skill).model_dump() for skill in ALL_FOUR}
    payload.pop("lexical_resource")
    with pytest.raises(ValidationError):
        LearningEvidenceSet.model_validate(payload)


def test_evidence_set_rejects_extra_or_mismatched_skill() -> None:
    payload = {skill: make_evidence(skill).model_dump() for skill in ALL_FOUR}
    payload["grammar"] = make_evidence("task_response").model_dump()
    with pytest.raises(ValidationError):
        LearningEvidenceSet.model_validate(payload)

    mismatched = {skill: make_evidence(skill).model_dump() for skill in ALL_FOUR}
    mismatched["lexical_resource"] = make_evidence("task_response").model_dump()
    with pytest.raises(ValidationError, match="skill"):
        LearningEvidenceSet.model_validate(mismatched)


def test_state_set_rejects_missing_or_mismatched_skill() -> None:
    payload = {skill: make_state(skill).model_dump() for skill in ALL_FOUR}
    payload.pop("task_response")
    with pytest.raises(ValidationError):
        LearnerSkillStateSet.model_validate(payload)

    mismatched = {skill: make_state(skill).model_dump() for skill in ALL_FOUR}
    mismatched["coherence_and_cohesion"] = make_state("task_response").model_dump()
    with pytest.raises(ValidationError, match="skill"):
        LearnerSkillStateSet.model_validate(mismatched)


# ---------------------------------------------------------------------------
# Set consistency (reject mixed logical sources)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "different"),
    [
        ("learner_id", 2),
        ("learning_update_id", 2),
        ("writing_evaluation_id", 2),
        ("source_created_at", datetime(2026, 1, 1, 13, 0, 0)),
        ("source_attempt_id", 2),
    ],
)
def test_evidence_set_rejects_mixed_identity(field: str, different: object) -> None:
    payload = {skill: make_evidence(skill).model_dump() for skill in ALL_FOUR}
    payload["lexical_resource"][field] = different
    with pytest.raises(ValidationError, match=field):
        LearningEvidenceSet.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "different"),
    [
        ("provider", "other-provider"),
        ("model", "other-model"),
        ("prompt_version", "other-prompt"),
        ("rubric_version", "other-rubric"),
        ("scoring_policy_version", "other-scoring"),
        ("thinking_mode", "enabled"),
    ],
)
def test_evidence_set_rejects_mixed_provenance(field: str, different: str) -> None:
    payload = {skill: make_evidence(skill).model_dump() for skill in ALL_FOUR}
    payload["lexical_resource"]["provenance"][field] = different
    with pytest.raises(ValidationError, match="provenance"):
        LearningEvidenceSet.model_validate(payload)


def test_state_set_rejects_mixed_learner_id() -> None:
    payload = {skill: make_state(skill).model_dump() for skill in ALL_FOUR}
    payload["lexical_resource"]["learner_id"] = 2
    with pytest.raises(ValidationError, match="learner_id"):
        LearnerSkillStateSet.model_validate(payload)


def test_state_set_rejects_mixed_state_policy_version() -> None:
    # state_policy_version is a single-value Literal, so a mixed version is
    # rejected before it can reach the set-level consistency check.
    payload = {skill: make_state(skill).model_dump() for skill in ALL_FOUR}
    payload["lexical_resource"]["state_policy_version"] = "writing-state-ewma-v2"
    with pytest.raises(ValidationError, match="state_policy_version"):
        LearnerSkillStateSet.model_validate(payload)


def test_state_set_rejects_extra_field() -> None:
    payload = {skill: make_state(skill).model_dump() for skill in ALL_FOUR}
    payload["extra"] = make_state("task_response").model_dump()
    with pytest.raises(ValidationError):
        LearnerSkillStateSet.model_validate(payload)


# ---------------------------------------------------------------------------
# Version fields and blank rejection
# ---------------------------------------------------------------------------


def test_update_version_fields_are_frozen() -> None:
    payload = {
        "id": 1,
        "learner_id": 1,
        "writing_evaluation_id": 1,
        "skill_taxonomy_version": "writing-core-v1",
        "state_policy_version": "writing-state-ewma-v1",
        "planner_version": "planner-v1",
        "created_at": _dt(),
    }
    assert LearningUpdate.model_validate(payload).skill_taxonomy_version == "writing-core-v1"

    bad = dict(payload)
    bad["skill_taxonomy_version"] = "writing-core-v2"
    with pytest.raises(ValidationError):
        LearningUpdate.model_validate(bad)


def test_planner_version_is_non_blank_but_value_deferred() -> None:
    payload = {
        "id": 1,
        "learner_id": 1,
        "writing_evaluation_id": 1,
        "skill_taxonomy_version": "writing-core-v1",
        "state_policy_version": "writing-state-ewma-v1",
        "planner_version": " ",
        "created_at": _dt(),
    }
    with pytest.raises(ValidationError):
        LearningUpdate.model_validate(payload)


def test_state_policy_version_is_frozen() -> None:
    with pytest.raises(ValidationError):
        make_state("task_response", state_policy_version="writing-state-ewma-v2")


# ---------------------------------------------------------------------------
# Extra fields and safe serialization
# ---------------------------------------------------------------------------


def test_schemas_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        LearnerCreate(writing_target_band=band("6.5"), unexpected="x")

    with pytest.raises(ValidationError):
        make_evidence("task_response", unexpected="x")


def test_evidence_serializes_safely() -> None:
    evidence = make_evidence("lexical_resource", observed="7.0")
    dumped = evidence.model_dump()

    assert dumped["skill"] == "lexical_resource"
    assert dumped["observed_band"] == {"value": Decimal("7.0")}
    assert dumped["source_attempt_id"] == 1
    assert dumped["provenance"]["thinking_mode"] == "disabled"

    as_json = evidence.model_dump_json()
    assert "lexical_resource" in as_json


@pytest.mark.parametrize(
    ("value", "expected_json"),
    [
        ("6.50", '"6.50"'),
        ("6.56", '"6.56"'),
        ("0.00", '"0.00"'),
        ("9.00", '"9.00"'),
    ],
)
def test_derived_state_json_serializes_exactly_two_decimals(value: str, expected_json: str) -> None:
    state = make_state("task_response", estimated=value)
    assert f'"estimated_band":{expected_json}' in state.model_dump_json()


def test_derived_state_python_value_remains_decimal() -> None:
    state = make_state("task_response", estimated="6.50")
    assert isinstance(state.estimated_band, Decimal)
    assert state.estimated_band == Decimal("6.50")
    assert state.model_dump()["estimated_band"] == Decimal("6.50")
    assert state.model_dump()["estimated_band"] != "6.50"


def test_unobserved_state_serializes_null_estimate() -> None:
    state = make_state("task_response", estimated=None, evidence_count=0, last_evidence_id=None, revision=0)
    dumped = state.model_dump()
    assert dumped["estimated_band"] is None
    assert dumped["last_evidence_id"] is None
    assert dumped["evidence_count"] == 0
    assert '"estimated_band":null' in state.model_dump_json()
