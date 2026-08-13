"""Metadata tests for Phase 2 writing persistence models."""

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    inspect,
)
from sqlalchemy.orm import InstrumentedAttribute

from app.db.base import Base
from app.models import WritingAttempt, WritingEvaluation


ATTEMPT_COLUMNS = {
    "id",
    "question",
    "essay",
    "word_count",
    "created_at",
}
EVALUATION_COLUMNS = {
    "id",
    "attempt_id",
    "task_response_band",
    "coherence_and_cohesion_band",
    "lexical_resource_band",
    "grammatical_range_and_accuracy_band",
    "product_band",
    "criteria_feedback",
    "strengths",
    "weaknesses",
    "error_tags",
    "recommended_skills",
    "feedback",
    "provider",
    "model",
    "prompt_version",
    "rubric_version",
    "scoring_policy_version",
    "thinking_mode",
    "created_at",
}
BAND_COLUMNS = {
    "task_response_band",
    "coherence_and_cohesion_band",
    "lexical_resource_band",
    "grammatical_range_and_accuracy_band",
    "product_band",
}


def constraint_names(table_name: str) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {constraint.name for constraint in table.constraints if constraint.name}


def test_writing_models_register_expected_metadata() -> None:
    assert set(Base.metadata.tables) >= {
        "writing_attempts",
        "writing_evaluations",
    }
    assert set(WritingAttempt.__table__.columns.keys()) == ATTEMPT_COLUMNS
    assert set(WritingEvaluation.__table__.columns.keys()) == EVALUATION_COLUMNS


def test_attempt_columns_have_explicit_types_defaults_and_constraints() -> None:
    table = WritingAttempt.__table__

    assert isinstance(table.c.id.type, BigInteger)
    assert table.c.id.primary_key
    assert isinstance(table.c.question.type, Text)
    assert isinstance(table.c.essay.type, Text)
    assert isinstance(table.c.word_count.type, Integer)
    assert isinstance(table.c.created_at.type, DateTime)
    assert table.c.created_at.type.timezone is True
    assert table.c.created_at.server_default is not None
    assert constraint_names(table.name) >= {
        "ck_writing_attempt_question_nonblank",
        "ck_writing_attempt_essay_nonblank",
        "ck_writing_attempt_word_count_positive",
    }
    assert {index.name for index in table.indexes} == {
        "ix_writing_attempt_created_at"
    }


def test_evaluation_columns_preserve_bands_structured_feedback_and_metadata() -> None:
    table = WritingEvaluation.__table__

    assert isinstance(table.c.id.type, BigInteger)
    assert table.c.id.primary_key
    for name in BAND_COLUMNS:
        column_type = table.c[name].type
        assert isinstance(column_type, Numeric)
        assert column_type.precision == 2
        assert column_type.scale == 1

    for name in {
        "criteria_feedback",
        "strengths",
        "weaknesses",
        "error_tags",
        "recommended_skills",
    }:
        assert isinstance(table.c[name].type, JSON)

    assert isinstance(table.c.feedback.type, Text)
    assert isinstance(table.c.provider.type, String)
    assert table.c.provider.type.length == 64
    assert isinstance(table.c.model.type, String)
    assert table.c.model.type.length == 255
    assert isinstance(table.c.prompt_version.type, String)
    assert table.c.prompt_version.type.length == 64
    assert table.c.rubric_version.type.length == 64
    assert table.c.scoring_policy_version.type.length == 64
    assert table.c.thinking_mode.type.length == 16
    assert table.c.created_at.server_default is not None
    assert {index.name for index in table.indexes} == {
        "ix_writing_evaluation_created_at"
    }


def test_evaluation_constraints_cover_every_band_and_nonblank_metadata() -> None:
    names = constraint_names(WritingEvaluation.__tablename__)

    assert names >= {
        *(f"ck_writing_evaluation_{name}" for name in BAND_COLUMNS),
        "ck_writing_evaluation_feedback_nonblank",
        "ck_writing_evaluation_provider_nonblank",
        "ck_writing_evaluation_model_nonblank",
        "ck_writing_evaluation_prompt_version_nonblank",
        "ck_writing_evaluation_rubric_version_nonblank",
        "ck_writing_evaluation_scoring_policy_version_nonblank",
        "ck_writing_evaluation_thinking_mode",
        "uq_writing_evaluation_attempt_id",
    }
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in WritingEvaluation.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    for name in BAND_COLUMNS:
        sql = checks[f"ck_writing_evaluation_{name}"]
        assert f"{name} >= 0" in sql
        assert f"{name} <= 9" in sql
        assert f"floor({name} * 2)" in sql


def test_attempt_evaluation_ownership_is_one_to_one_and_cascades() -> None:
    foreign_keys = list(WritingEvaluation.__table__.c.attempt_id.foreign_keys)

    assert len(foreign_keys) == 1
    foreign_key = foreign_keys[0]
    assert foreign_key.target_fullname == "writing_attempts.id"
    assert foreign_key.name == "fk_writing_evaluation_attempt_id"
    assert foreign_key.ondelete == "CASCADE"
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {"attempt_id"}
        for constraint in WritingEvaluation.__table__.constraints
    )

    attempt_relationship = inspect(WritingAttempt).relationships.evaluation
    evaluation_relationship = inspect(WritingEvaluation).relationships.attempt
    assert attempt_relationship.uselist is False
    assert attempt_relationship.single_parent
    assert attempt_relationship.passive_deletes is True
    assert "delete" in attempt_relationship.cascade
    assert "delete-orphan" in attempt_relationship.cascade
    assert attempt_relationship.back_populates == "attempt"
    assert evaluation_relationship.back_populates == "evaluation"


def test_models_use_mapped_instrumented_attributes_without_domain_services() -> None:
    assert isinstance(WritingAttempt.id, InstrumentedAttribute)
    assert isinstance(WritingAttempt.evaluation, InstrumentedAttribute)
    assert isinstance(WritingEvaluation.id, InstrumentedAttribute)
    assert isinstance(WritingEvaluation.attempt, InstrumentedAttribute)
    assert not {
        "learner_id",
        "mastery",
        "memory",
        "plan",
        "agent_state",
    } & (ATTEMPT_COLUMNS | EVALUATION_COLUMNS)
