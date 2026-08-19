"""Metadata tests for Phase 3 learning persistence models (P3-04).

These tests inspect SQLAlchemy metadata to verify that the models encode the
accepted P3-02, P3-03, and P3-08 contracts at the database-model layer. They
contain no extraction, state-update, planner, service, or API behavior.
"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    inspect,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import InstrumentedAttribute

from app.db.base import Base
from app.models import (
    Learner,
    LearnerSkillState,
    LearningEvidence,
    LearningUpdate,
    PracticeRecommendation,
    WritingAttempt,
    WritingEvaluation,
)

CANONICAL_SKILLS = (
    "task_response",
    "coherence_and_cohesion",
    "lexical_resource",
    "grammatical_range_and_accuracy",
)

LEARNER_COLUMNS = {"id", "writing_target_band", "created_at", "updated_at"}
LEARNING_UPDATE_COLUMNS = {
    "id",
    "learner_id",
    "writing_evaluation_id",
    "skill_taxonomy_version",
    "state_policy_version",
    "planner_version",
    "created_at",
}
LEARNING_EVIDENCE_COLUMNS = {
    "id",
    "learning_update_id",
    "learner_id",
    "writing_evaluation_id",
    "skill",
    "observed_band",
    "source_created_at",
    "source_attempt_id",
    "provider",
    "model",
    "prompt_version",
    "rubric_version",
    "scoring_policy_version",
    "thinking_mode",
    "created_at",
}
LEARNER_SKILL_STATE_COLUMNS = {
    "learner_id",
    "skill",
    "estimated_band",
    "evidence_count",
    "state_policy_version",
    "last_evidence_id",
    "revision",
    "updated_at",
}
PRACTICE_RECOMMENDATION_COLUMNS = {
    "id",
    "learning_update_id",
    "learner_id",
    "decision_type",
    "target_skill",
    "learner_target_band",
    "current_estimate",
    "reason_codes",
    "planner_version",
    "state_snapshot",
    "planner_context_snapshot",
    "created_at",
}


def constraint_names(table_name: str) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {constraint.name for constraint in table.constraints if constraint.name}


def check_sql(table_name: str) -> dict[str, str]:
    table = Base.metadata.tables[table_name]
    return {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }


def foreign_key_constraints(table_name: str) -> dict[str, ForeignKeyConstraint]:
    table = Base.metadata.tables[table_name]
    return {
        constraint.name: constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }


def test_all_phase3_tables_register_in_metadata() -> None:
    assert set(Base.metadata.tables) >= {
        "learners",
        "learning_updates",
        "learning_evidence",
        "learner_skill_states",
        "practice_recommendations",
        "writing_attempts",
        "writing_evaluations",
    }


def test_model_columns_match_expected_contracts() -> None:
    assert set(Learner.__table__.columns.keys()) == LEARNER_COLUMNS
    assert set(LearningUpdate.__table__.columns.keys()) == LEARNING_UPDATE_COLUMNS
    assert set(LearningEvidence.__table__.columns.keys()) == LEARNING_EVIDENCE_COLUMNS
    assert set(LearnerSkillState.__table__.columns.keys()) == LEARNER_SKILL_STATE_COLUMNS
    assert set(PracticeRecommendation.__table__.columns.keys()) == PRACTICE_RECOMMENDATION_COLUMNS


def _fk_to(table_name: str, column_name: str, target: str) -> ForeignKey:
    column = Base.metadata.tables[table_name].c[column_name]
    return next(
        foreign_key
        for foreign_key in column.foreign_keys
        if foreign_key.target_fullname == target
    )


def test_big_integer_ids_and_foreign_keys() -> None:
    assert isinstance(Learner.__table__.c.id.type, BigInteger)
    assert Learner.__table__.c.id.primary_key
    assert isinstance(LearningUpdate.__table__.c.id.type, BigInteger)
    assert isinstance(LearningUpdate.__table__.c.learner_id.type, BigInteger)
    assert isinstance(LearningUpdate.__table__.c.writing_evaluation_id.type, BigInteger)
    assert isinstance(LearningEvidence.__table__.c.id.type, BigInteger)
    assert isinstance(LearningEvidence.__table__.c.source_attempt_id.type, BigInteger)
    assert isinstance(LearnerSkillState.__table__.c.learner_id.type, BigInteger)
    assert isinstance(PracticeRecommendation.__table__.c.id.type, BigInteger)
    assert isinstance(PracticeRecommendation.__table__.c.learning_update_id.type, BigInteger)

    assert _fk_to("learning_updates", "learner_id", "learners.id").name == "fk_learning_update_learner_id"
    assert _fk_to("learning_updates", "writing_evaluation_id", "writing_evaluations.id").name == "fk_learning_update_writing_evaluation_id"
    assert _fk_to("learning_evidence", "source_attempt_id", "writing_attempts.id").name == "fk_learning_evidence_source_attempt_id"
    assert _fk_to("learner_skill_states", "learner_id", "learners.id").name == "fk_learner_skill_state_learner_id"
    assert _fk_to("practice_recommendations", "learner_id", "learners.id").name == "fk_practice_recommendation_learner_id"


def test_numeric_precision_split_between_half_band_and_derived_state() -> None:
    target = Learner.__table__.c.writing_target_band.type
    observed = LearningEvidence.__table__.c.observed_band.type
    estimated = LearnerSkillState.__table__.c.estimated_band.type
    current = PracticeRecommendation.__table__.c.current_estimate.type
    recommendation_target = PracticeRecommendation.__table__.c.learner_target_band.type

    for column_type in (target, observed, recommendation_target):
        assert isinstance(column_type, Numeric)
        assert column_type.precision == 2
        assert column_type.scale == 1

    for column_type in (estimated, current):
        assert isinstance(column_type, Numeric)
        assert column_type.precision == 3
        assert column_type.scale == 2


def test_derived_state_storage_is_not_half_band_scale() -> None:
    estimated = LearnerSkillState.__table__.c.estimated_band
    assert estimated.nullable is True
    assert estimated.type.scale == 2


def test_half_band_check_constraints_are_explicit() -> None:
    learner_checks = check_sql("learners")
    evidence_checks = check_sql("learning_evidence")
    recommendation_checks = check_sql("practice_recommendations")

    for sql in (
        learner_checks["ck_learner_writing_target_band"],
        evidence_checks["ck_learning_evidence_observed_band"],
        recommendation_checks["ck_practice_recommendation_learner_target_band"],
    ):
        assert " >= 0" in sql
        assert " <= 9" in sql
        assert "floor(" in sql


def test_canonical_skill_constraints_cover_every_skill() -> None:
    evidence_checks = check_sql("learning_evidence")
    state_checks = check_sql("learner_skill_states")
    recommendation_checks = check_sql("practice_recommendations")

    for sql in (
        evidence_checks["ck_learning_evidence_skill"],
        state_checks["ck_learner_skill_state_skill"],
    ):
        for skill in CANONICAL_SKILLS:
            assert repr(skill) in sql

    assert "target_skill IS NULL OR" in recommendation_checks["ck_practice_recommendation_target_skill"]
    for skill in CANONICAL_SKILLS:
        assert repr(skill) in recommendation_checks["ck_practice_recommendation_target_skill"]


def test_writing_evaluation_id_is_globally_unique_in_updates() -> None:
    assert LearningUpdate.__table__.c.writing_evaluation_id.unique is True
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {"writing_evaluation_id"}
        for constraint in LearningUpdate.__table__.constraints
    )


def test_one_state_row_per_learner_and_skill() -> None:
    table = LearnerSkillState.__table__
    assert table.c.learner_id.primary_key
    assert table.c.skill.primary_key
    assert {column.name for column in table.primary_key.columns} == {
        "learner_id",
        "skill",
    }


def test_one_evidence_row_per_update_and_skill() -> None:
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {"learning_update_id", "skill"}
        for constraint in LearningEvidence.__table__.constraints
    )


def test_one_recommendation_per_learning_update() -> None:
    assert PracticeRecommendation.__table__.c.learning_update_id.unique is True
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {"learning_update_id"}
        for constraint in PracticeRecommendation.__table__.constraints
    )


def test_composite_evidence_update_ownership_foreign_key() -> None:
    fk = foreign_key_constraints("learning_evidence")[
        "fk_learning_evidence_learning_update_ownership"
    ]
    assert {column.name for column in fk.columns} == {
        "learning_update_id",
        "learner_id",
        "writing_evaluation_id",
    }
    assert {element.column.name for element in fk.elements} == {
        "id",
        "learner_id",
        "writing_evaluation_id",
    }
    assert fk.referred_table.name == "learning_updates"
    assert fk.ondelete == "RESTRICT"


def test_composite_recommendation_update_ownership_foreign_key() -> None:
    fk = foreign_key_constraints("practice_recommendations")[
        "fk_practice_recommendation_learning_update_ownership"
    ]
    assert {column.name for column in fk.columns} == {"learning_update_id", "learner_id"}
    assert fk.referred_table.name == "learning_updates"
    assert fk.ondelete == "RESTRICT"

    assert _fk_to("practice_recommendations", "learner_id", "learners.id").name == (
        "fk_practice_recommendation_learner_id"
    )


def test_learning_update_exposes_recommendation_ownership_candidate_key() -> None:
    update_constraints = {
        constraint.name: constraint
        for constraint in LearningUpdate.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    # PostgreSQL requires the exact referenced column set (id, learner_id) to be
    # backed by a matching unique candidate key on learning_updates.
    candidate = update_constraints["uq_learning_update_learner_identity"]
    assert candidate.name == "uq_learning_update_learner_identity"
    assert {column.name for column in candidate.columns} == {"id", "learner_id"}

    # The recommendation composite FK must reference exactly this candidate key.
    fk = foreign_key_constraints("practice_recommendations")[
        "fk_practice_recommendation_learning_update_ownership"
    ]
    assert {column.name for column in fk.columns} == {"learning_update_id", "learner_id"}
    assert {element.column.name for element in fk.elements} == {"id", "learner_id"}
    assert fk.referred_table.name == "learning_updates"

    # The pre-existing 3-column candidate key is preserved alongside it.
    assert "uq_learning_update_identity" in update_constraints
    assert {column.name for column in update_constraints["uq_learning_update_identity"].columns} == {
        "id",
        "learner_id",
        "writing_evaluation_id",
    }


def test_last_evidence_ownership_foreign_key() -> None:
    fk = foreign_key_constraints("learner_skill_states")[
        "fk_learner_skill_state_last_evidence_ownership"
    ]
    assert {column.name for column in fk.columns} == {
        "last_evidence_id",
        "learner_id",
        "skill",
    }
    assert fk.referred_table.name == "learning_evidence"
    assert fk.ondelete == "RESTRICT"


def test_state_observed_unobserved_database_invariant() -> None:
    checks = check_sql("learner_skill_states")
    consistency = checks["ck_learner_skill_state_observed_consistency"]
    assert "evidence_count = 0" in consistency
    assert "estimated_band IS NULL" in consistency
    assert "last_evidence_id IS NULL" in consistency
    assert "revision = 0" in consistency
    assert "evidence_count > 0" in consistency
    assert "estimated_band IS NOT NULL" in consistency
    assert "last_evidence_id IS NOT NULL" in consistency
    assert "revision >= 1" in consistency
    assert "evidence_count >= 0" in checks["ck_learner_skill_state_evidence_count_nonnegative"]
    assert "revision >= 0" in checks["ck_learner_skill_state_revision_nonnegative"]


def test_nonblank_policy_version_constraints() -> None:
    update_checks = check_sql("learning_updates")
    assert "skill_taxonomy_version" in update_checks["ck_learning_update_skill_taxonomy_version_nonblank"]
    assert "state_policy_version" in update_checks["ck_learning_update_state_policy_version_nonblank"]
    assert "planner_version" in update_checks["ck_learning_update_planner_version_nonblank"]
    assert "state_policy_version" in check_sql("learner_skill_states")[
        "ck_learner_skill_state_state_policy_version_nonblank"
    ]
    assert "planner_version" in check_sql("practice_recommendations")[
        "ck_practice_recommendation_planner_version_nonblank"
    ]


def test_reason_code_and_decision_constraints() -> None:
    checks = check_sql("practice_recommendations")

    assert "decision_type IN ('practice', 'no_practice')" in checks[
        "ck_practice_recommendation_decision_type"
    ]
    assert "jsonb_typeof(reason_codes) = 'array'" in checks[
        "ck_practice_recommendation_reason_codes_array"
    ]
    assert "jsonb_typeof(state_snapshot) = 'object'" in checks[
        "ck_practice_recommendation_state_snapshot_object"
    ]
    snapshot_check = checks[
        "ck_practice_recommendation_planner_context_snapshot_object"
    ]
    assert "planner_context_snapshot IS NULL" in snapshot_check
    assert "jsonb_typeof(planner_context_snapshot) = 'object'" in snapshot_check

    sequences = checks["ck_practice_recommendation_reason_sequences"]
    for sequence in (
        '["largest_target_gap"]',
        '["largest_target_gap","priority_tiebreak"]',
        '["largest_target_gap","insufficient_evidence"]',
        '["largest_target_gap","priority_tiebreak","insufficient_evidence"]',
        '["target_achieved"]',
        '["target_achieved","insufficient_evidence"]',
        '["cold_start"]',
        '["incomplete_state"]',
        '["target_unset"]',
    ):
        assert sequence in sequences

    decision = checks["ck_practice_recommendation_reason_decision"]
    assert "decision_type = 'practice'" in decision
    assert "decision_type = 'no_practice'" in decision

    shape = checks["ck_practice_recommendation_decision_shape"]
    assert "decision_type = 'practice'" in shape
    assert "target_skill IS NOT NULL" in shape
    assert "current_estimate IS NOT NULL" in shape
    assert "decision_type = 'no_practice'" in shape
    assert "target_skill IS NULL" in shape
    assert "current_estimate IS NULL" in shape


def test_target_unset_nullability_constraint() -> None:
    sql = check_sql("practice_recommendations")[
        "ck_practice_recommendation_target_band_nullability"
    ]
    assert '["target_unset"]' in sql
    assert "learner_target_band IS NULL" in sql
    assert "learner_target_band IS NOT NULL" in sql


def test_state_snapshot_requires_four_canonical_keys() -> None:
    sql = check_sql("practice_recommendations")[
        "ck_practice_recommendation_snapshot_skills"
    ]
    for skill in CANONICAL_SKILLS:
        assert repr(skill) in sql


def test_reason_codes_and_snapshot_use_structured_jsonb() -> None:
    assert isinstance(PracticeRecommendation.__table__.c.reason_codes.type, JSONB)
    assert isinstance(PracticeRecommendation.__table__.c.state_snapshot.type, JSONB)
    snapshot = PracticeRecommendation.__table__.c.planner_context_snapshot
    assert isinstance(snapshot.type, JSONB)
    assert snapshot.nullable is True


def test_canonical_replay_index_exists() -> None:
    table = LearningEvidence.__table__
    replay = next(
        index
        for index in table.indexes
        if index.name == "ix_learning_evidence_canonical_replay"
    )
    assert [column.name for column in replay.columns] == [
        "learner_id",
        "skill",
        "source_created_at",
        "source_attempt_id",
    ]


def test_server_timestamp_defaults() -> None:
    for table, columns in (
        (Learner.__table__, {"created_at", "updated_at"}),
        (LearningUpdate.__table__, {"created_at"}),
        (LearningEvidence.__table__, {"created_at"}),
        (LearnerSkillState.__table__, {"updated_at"}),
        (PracticeRecommendation.__table__, {"created_at"}),
    ):
        for column in columns:
            assert table.c[column].server_default is not None
            assert table.c[column].type.timezone is True


def test_relationships_cardinality_and_back_populates() -> None:
    assert inspect(Learner).relationships.learning_updates.uselist is True
    assert inspect(Learner).relationships.skill_states.uselist is True
    assert inspect(Learner).relationships.recommendations.uselist is True
    assert inspect(LearningUpdate).relationships.learner.uselist is False
    assert inspect(LearningUpdate).relationships.evidence.uselist is True
    assert inspect(LearningUpdate).relationships.recommendation.uselist is False
    assert inspect(LearningEvidence).relationships.learning_update.uselist is False
    assert inspect(LearnerSkillState).relationships.learner.uselist is False
    assert inspect(PracticeRecommendation).relationships.learning_update.uselist is False
    assert inspect(PracticeRecommendation).relationships.learner.uselist is False

    assert inspect(Learner).relationships.learning_updates.back_populates == "learner"
    assert inspect(LearningUpdate).relationships.learner.back_populates == "learning_updates"
    assert inspect(LearningUpdate).relationships.evidence.back_populates == "learning_update"
    assert inspect(LearningEvidence).relationships.learning_update.back_populates == "evidence"
    assert inspect(LearningUpdate).relationships.recommendation.back_populates == "learning_update"
    assert inspect(PracticeRecommendation).relationships.learning_update.back_populates == "recommendation"
    assert inspect(Learner).relationships.skill_states.back_populates == "learner"
    assert inspect(LearnerSkillState).relationships.learner.back_populates == "skill_states"
    assert inspect(Learner).relationships.recommendations.back_populates == "learner"
    assert inspect(PracticeRecommendation).relationships.learner.back_populates == "recommendations"


def test_no_learner_columns_leak_into_phase2_models() -> None:
    phase2_columns = set(WritingAttempt.__table__.columns) | set(WritingEvaluation.__table__.columns)
    assert not {"learner_id", "skill", "evidence", "recommendation"} & {
        column.name for column in phase2_columns
    }


def test_models_contain_no_behavioral_methods() -> None:
    for model in (
        Learner,
        LearningUpdate,
        LearningEvidence,
        LearnerSkillState,
        PracticeRecommendation,
    ):
        for name, value in model.__dict__.items():
            if name.startswith("_"):
                continue
            assert not callable(value) or isinstance(value, InstrumentedAttribute), (
                f"{model.__name__}.{name} must not be a behavior method"
            )


# ---------------------------------------------------------------------------
# Schema / policy alignment
# ---------------------------------------------------------------------------


def test_learner_model_matches_learner_schema() -> None:
    from app.schemas.learner import LearnerCreate

    assert {field for field in LearnerCreate.model_fields} == {"writing_target_band"}
    assert set(Learner.__table__.columns.keys()) == LEARNER_COLUMNS


def test_learning_update_versions_are_not_db_frozen() -> None:
    # Versions are persisted history, not a single DB-level literal.
    table = LearningUpdate.__table__
    assert isinstance(table.c.skill_taxonomy_version.type, String)
    assert isinstance(table.c.state_policy_version.type, String)
    assert isinstance(table.c.planner_version.type, String)
    for column in ("skill_taxonomy_version", "state_policy_version", "planner_version"):
        assert not any(
            isinstance(constraint, CheckConstraint) and column in str(constraint.sqltext) and " IN (" in str(constraint.sqltext)
            for constraint in table.constraints
        )


def test_learning_evidence_matches_evidence_schema_fields() -> None:
    from app.schemas.learner import LearningEvidence as EvidenceSchema

    schema_fields = {
        "id",
        "learning_update_id",
        "learner_id",
        "writing_evaluation_id",
        "skill",
        "observed_band",
        "source_created_at",
        "source_attempt_id",
        "provenance",
        "created_at",
    }
    assert {field for field in EvidenceSchema.model_fields} == schema_fields
    # Provenance fields are flattened into the persistence model.
    for column in (
        "provider",
        "model",
        "prompt_version",
        "rubric_version",
        "scoring_policy_version",
        "thinking_mode",
    ):
        assert column in LEARNING_EVIDENCE_COLUMNS


def test_learner_skill_state_matches_state_schema_fields() -> None:
    from app.schemas.learner import LearnerSkillState as StateSchema

    assert {field for field in StateSchema.model_fields} == {
        "learner_id",
        "skill",
        "estimated_band",
        "evidence_count",
        "last_evidence_id",
        "state_policy_version",
        "revision",
        "updated_at",
    }


def test_recommendation_matches_planning_decision_fields() -> None:
    from app.schemas.planning import PracticeRecommendationDecision

    assert {field for field in PracticeRecommendationDecision.model_fields} == {
        "decision_type",
        "target_skill",
        "learner_target_band",
        "current_estimate",
        "reason_codes",
        "planner_version",
        "state_snapshot",
    }
