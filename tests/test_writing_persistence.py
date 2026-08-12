"""PostgreSQL integration tests for atomic writing persistence."""

from collections.abc import Generator
from decimal import Decimal
from unittest.mock import Mock

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import Engine, event, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.db.session import create_db_engine, create_session_factory
from app.models import WritingAttempt, WritingEvaluation
from app.schemas.writing import (
    WritingCriterion,
    WritingEvaluationResult,
    WritingSubmission,
)
from app.services.writing_persistence import (
    WritingEvaluationPersistenceService,
    WritingPersistenceError,
)


pytestmark = pytest.mark.integration


@pytest.fixture
def writing_engine(database_url: str) -> Generator[Engine, None, None]:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")
    engine = create_db_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE writing_evaluations, writing_attempts "
                "RESTART IDENTITY CASCADE"
            )
        )
    try:
        yield engine
    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "TRUNCATE writing_evaluations, writing_attempts "
                    "RESTART IDENTITY CASCADE"
                )
            )
        engine.dispose()


@pytest.fixture
def writing_session(writing_engine: Engine) -> Generator[Session, None, None]:
    factory = create_session_factory(writing_engine)
    with factory() as session:
        yield session


def submission() -> WritingSubmission:
    return WritingSubmission(
        question="Discuss both views.",
        essay="A short but valid response.",
    )


def evaluation(
    *,
    word_count: int = 5,
) -> WritingEvaluationResult:
    criterion = {
        "band": {"value": "6.5"},
        "evidence": ["Relevant evidence."],
        "feedback": "Develop this criterion.",
    }
    return WritingEvaluationResult.model_validate(
        {
            "criteria": {
                item.value: criterion
                for item in WritingCriterion
            },
            "strengths": ["Clear position."],
            "weaknesses": ["Support remains general."],
            "error_tags": ["article-use"],
            "recommended_skills": ["supporting examples"],
            "feedback": "Use more precise evidence.",
            "metadata": {
                "provider": "fake-provider",
                "model": "fake-model",
                "prompt_version": "writing-v1",
            },
            "word_count": word_count,
        }
    )


def row_counts(engine: Engine) -> tuple[int, int]:
    factory = create_session_factory(engine)
    with factory() as session:
        return (
            session.scalar(select(func.count()).select_from(WritingAttempt)) or 0,
            session.scalar(select(func.count()).select_from(WritingEvaluation))
            or 0,
        )


def test_persistence_writes_complete_pair_and_returns_committed_ids(
    writing_engine: Engine,
    writing_session: Session,
) -> None:
    persisted = WritingEvaluationPersistenceService(writing_session).persist(
        submission(),
        evaluation(),
    )

    assert persisted.attempt_id == 1
    assert persisted.evaluation_id == 1
    factory = create_session_factory(writing_engine)
    with factory() as verification:
        attempt = verification.scalar(
            select(WritingAttempt)
            .options(selectinload(WritingAttempt.evaluation))
            .where(WritingAttempt.id == persisted.attempt_id)
        )
        assert attempt is not None
        assert attempt.question == "Discuss both views."
        assert attempt.essay == "A short but valid response."
        assert attempt.word_count == 5
        assert attempt.evaluation is not None
        stored = attempt.evaluation
        assert stored.id == persisted.evaluation_id
        assert stored.attempt_id == persisted.attempt_id
        assert stored.task_response_band == Decimal("6.5")
        assert stored.coherence_and_cohesion_band == Decimal("6.5")
        assert stored.lexical_resource_band == Decimal("6.5")
        assert stored.grammatical_range_and_accuracy_band == Decimal("6.5")
        assert stored.product_band == Decimal("6.5")
        assert stored.criteria_feedback["task_response"] == {
            "evidence": ["Relevant evidence."],
            "feedback": "Develop this criterion.",
        }
        assert stored.strengths == ["Clear position."]
        assert stored.weaknesses == ["Support remains general."]
        assert stored.error_tags == ["article-use"]
        assert stored.recommended_skills == ["supporting examples"]
        assert stored.feedback == "Use more precise evidence."
        assert stored.provider == "fake-provider"
        assert stored.model == "fake-model"
        assert stored.prompt_version == "writing-v1"
        assert stored.created_at is not None


def test_invalid_evaluation_is_rejected_before_any_write(
    writing_engine: Engine,
    writing_session: Session,
) -> None:
    invalid = {"word_count": 5}

    with pytest.raises(ValidationError):
        WritingEvaluationPersistenceService(writing_session).persist(
            submission(),
            invalid,  # type: ignore[arg-type]
        )

    assert row_counts(writing_engine) == (0, 0)


def test_word_count_mismatch_is_rejected_before_any_write(
    writing_engine: Engine,
    writing_session: Session,
) -> None:
    with pytest.raises(ValueError, match="word_count"):
        WritingEvaluationPersistenceService(writing_session).persist(
            submission(),
            evaluation(word_count=999),
        )

    assert row_counts(writing_engine) == (0, 0)


def test_flush_failure_rolls_back_without_partial_attempt(
    writing_engine: Engine,
    writing_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flush = Mock(side_effect=SQLAlchemyError("private flush details"))
    monkeypatch.setattr(writing_session, "flush", flush)

    with pytest.raises(WritingPersistenceError) as captured:
        WritingEvaluationPersistenceService(writing_session).persist(
            submission(),
            evaluation(),
        )

    assert flush.call_count == 1
    assert str(captured.value) == "Writing evaluation could not be persisted."
    assert "private flush details" not in str(captured.value)
    assert row_counts(writing_engine) == (0, 0)


def test_commit_failure_rolls_back_flushed_pair(
    writing_engine: Engine,
    writing_session: Session,
) -> None:
    def fail_commit(session: Session) -> None:
        raise SQLAlchemyError("private commit details")

    event.listen(writing_session, "before_commit", fail_commit)
    try:
        with pytest.raises(WritingPersistenceError) as captured:
            WritingEvaluationPersistenceService(writing_session).persist(
                submission(),
                evaluation(),
            )
    finally:
        event.remove(writing_session, "before_commit", fail_commit)

    assert str(captured.value) == "Writing evaluation could not be persisted."
    assert "private commit details" not in str(captured.value)
    assert row_counts(writing_engine) == (0, 0)
