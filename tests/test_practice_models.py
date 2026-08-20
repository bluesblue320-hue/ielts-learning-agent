"""P4-05 writing practice persistence model tests (metadata-level).

Real-PostgreSQL constraint enforcement is proven after the P4-06 migration
materializes these models; this module verifies the model structure encodes
the frozen Phase 4 invariants.
"""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from app.models.learning import PracticeRecommendation
from app.models.practice import WritingPractice


def _unique_names(table) -> set[str]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint) and constraint.name
    }


def _fks(table) -> list[ForeignKeyConstraint]:
    return [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]


def _checks(table) -> dict[str, str]:
    return {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name
    }


def test_writing_practice_table_name() -> None:
    assert WritingPractice.__tablename__ == "writing_practices"


def test_recommendation_idempotency_anchor_present() -> None:
    names = _unique_names(WritingPractice.__table__)
    assert "uq_writing_practice_recommendation_id" in names


def test_attempt_unique_anchor_present() -> None:
    names = _unique_names(WritingPractice.__table__)
    assert "uq_writing_practice_attempt_id" in names


def test_practice_recommendation_ownership_candidate_key_present() -> None:
    names = _unique_names(PracticeRecommendation.__table__)
    assert "uq_practice_recommendation_id_learner" in names
    candidate = next(
        c
        for c in PracticeRecommendation.__table__.constraints
        if isinstance(c, UniqueConstraint) and c.name == "uq_practice_recommendation_id_learner"
    )
    assert list(candidate.columns) == [
        PracticeRecommendation.__table__.c.id,
        PracticeRecommendation.__table__.c.learner_id,
    ]


def test_composite_ownership_fk_present() -> None:
    fks = _fks(WritingPractice.__table__)
    ownership = next(
        fk
        for fk in fks
        if fk.name == "fk_writing_practice_recommendation_ownership"
    )
    assert list(ownership.columns) == [
        WritingPractice.__table__.c.recommendation_id,
        WritingPractice.__table__.c.learner_id,
    ]
    target = list(ownership.elements)
    assert target[0].target_fullname == "practice_recommendations.id"
    assert target[1].target_fullname == "practice_recommendations.learner_id"
    assert ownership.ondelete == "RESTRICT"


def test_attempt_fk_restrict_and_nullable() -> None:
    attempt_fk = WritingPractice.__table__.c.attempt_id.foreign_keys
    assert len(attempt_fk) == 1
    fk = next(iter(attempt_fk))
    assert fk.target_fullname == "writing_attempts.id"
    assert fk.ondelete == "RESTRICT"
    assert WritingPractice.__table__.c.attempt_id.nullable


def test_lifecycle_state_check_constraint() -> None:
    checks = _checks(WritingPractice.__table__)
    lifecycle = checks["ck_writing_practice_lifecycle_state"]
    for state in ("generated", "submission_in_progress", "submitted"):
        assert state in str(lifecycle)


def test_attempt_nullability_check_constraint() -> None:
    checks = _checks(WritingPractice.__table__)
    assert "attempt_id IS NOT NULL" in str(checks["ck_writing_practice_attempt_nullability"])
    assert "attempt_id IS NULL" in str(checks["ck_writing_practice_attempt_nullability"])


def test_submission_state_matrix_check_constraint() -> None:
    checks = _checks(WritingPractice.__table__)
    matrix = str(checks["ck_writing_practice_submission_state_matrix"])
    for column in (
        "submission_fingerprint",
        "claim_token",
        "submission_claimed_at",
        "attempt_id",
    ):
        assert column in matrix


def test_generation_content_constraints_present() -> None:
    checks = _checks(WritingPractice.__table__)
    assert "ck_writing_practice_question_length" in checks
    assert "ck_writing_practice_objective_length" in checks
    assert "ck_writing_practice_instructions_array" in checks
    assert "ck_writing_practice_checkpoints_array" in checks
    assert "ck_writing_practice_generator_policy_version_nonblank" in checks
    assert "ck_writing_practice_provider_nonblank" in checks
    assert "ck_writing_practice_model_nonblank" in checks
    assert "ck_writing_practice_prompt_version_nonblank" in checks
    assert "ck_writing_practice_thinking_mode" in checks


def test_model_has_provenance_and_claim_columns() -> None:
    columns = set(WritingPractice.__table__.c.keys())
    for column in (
        "id",
        "learner_id",
        "recommendation_id",
        "target_skill",
        "question",
        "focus_objective",
        "instructions",
        "checkpoints",
        "generator_policy_version",
        "provider",
        "model",
        "prompt_version",
        "thinking_mode",
        "lifecycle_state",
        "submission_fingerprint",
        "claim_token",
        "submission_claimed_at",
        "attempt_id",
        "created_at",
        "updated_at",
    ):
        assert column in columns
