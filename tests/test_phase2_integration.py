"""Phase 2 end-to-end integration evidence against isolated PostgreSQL."""

from collections.abc import Generator
from contextlib import contextmanager
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies.writing import get_writing_provider
from app.db.session import (
    create_db_engine,
    create_session_factory,
    get_db_session,
)
from app.llm import LLMProvider
from app.main import create_app
from app.models import WritingAttempt, WritingEvaluation
from tests.fakes import FakeProvider


pytestmark = [pytest.mark.integration, pytest.mark.provider]


def valid_provider_payload() -> dict[str, object]:
    criterion = {
        "band": {"value": "6.5"},
        "evidence": ["Relevant evidence."],
        "feedback": "Develop this criterion.",
    }
    return {
        "criteria": {
            "task_response": criterion,
            "coherence_and_cohesion": criterion,
            "lexical_resource": criterion,
            "grammatical_range_and_accuracy": criterion,
        },
        "strengths": ["Clear position."],
        "weaknesses": ["Support remains general."],
        "error_tags": ["article-use"],
        "recommended_skills": ["supporting examples"],
        "feedback": "Use more precise evidence.",
        "metadata": {
            "provider": "untrusted-provider",
            "model": "untrusted-model",
            "prompt_version": "untrusted-version",
        },
    }


@pytest.fixture
def phase2_engine(database_url: str) -> Generator[Engine, None, None]:
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


@contextmanager
def integration_client(
    engine: Engine,
    provider: LLMProvider,
    *,
    fail_commit: bool = False,
) -> Generator[TestClient, None, None]:
    session_factory = create_session_factory(engine)

    def reject_commit(_session: Session) -> None:
        raise SQLAlchemyError("development-only commit failure sentinel")

    def session_override() -> Generator[Session, None, None]:
        with session_factory() as session:
            if fail_commit:
                event.listen(session, "before_commit", reject_commit)
            try:
                yield session
            finally:
                if fail_commit:
                    event.remove(session, "before_commit", reject_commit)

    application = create_app()
    application.dependency_overrides[get_writing_provider] = lambda: provider
    application.dependency_overrides[get_db_session] = session_override
    with TestClient(application) as client:
        yield client


def row_counts(engine: Engine) -> tuple[int, int]:
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        return (
            session.scalar(select(func.count()).select_from(WritingAttempt)) or 0,
            session.scalar(select(func.count()).select_from(WritingEvaluation)) or 0,
        )


def test_submission_traverses_api_and_stores_complete_migrated_pair(
    phase2_engine: Engine,
) -> None:
    provider = FakeProvider([valid_provider_payload()])
    with integration_client(phase2_engine, provider) as client:
        response = client.post(
            "/writing/evaluate",
            json={
                "question": "Discuss both views.",
                "essay": "A short but valid response.",
            },
        )

    assert response.status_code == 201
    assert response.json()["attempt_id"] == 1
    assert response.json()["evaluation"]["product_band"] == {"value": "6.5"}
    assert len(provider.requests) == 1

    session_factory = create_session_factory(phase2_engine)
    with session_factory() as session:
        revision = session.scalar(text("SELECT version_num FROM alembic_version"))
        attempt = session.scalar(
            select(WritingAttempt)
            .options(selectinload(WritingAttempt.evaluation))
            .where(WritingAttempt.id == 1)
        )
        assert revision == "0002_writing"
        assert attempt is not None
        assert attempt.word_count == 5
        assert attempt.evaluation is not None
        assert attempt.evaluation.product_band == Decimal("6.5")
        assert attempt.evaluation.provider == "fake-provider"
        assert attempt.evaluation.model == "fake-model"
        assert attempt.evaluation.prompt_version == "writing-v1"
        assert attempt.evaluation.error_tags == ["article-use"]


def test_invalid_provider_result_creates_no_attempt_or_evaluation(
    phase2_engine: Engine,
) -> None:
    provider = FakeProvider([{"raw_provider_body": "unsafe private value"}])
    with integration_client(phase2_engine, provider) as client:
        response = client.post(
            "/writing/evaluate",
            json={"question": "Why?", "essay": "A valid response."},
        )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_invalid_response"
    assert "unsafe private value" not in response.text
    assert len(provider.requests) == 1
    assert row_counts(phase2_engine) == (0, 0)


def test_database_commit_failure_rolls_back_complete_pair(
    phase2_engine: Engine,
) -> None:
    provider = FakeProvider([valid_provider_payload()])
    with integration_client(
        phase2_engine,
        provider,
        fail_commit=True,
    ) as client:
        response = client.post(
            "/writing/evaluate",
            json={"question": "Why?", "essay": "A valid response."},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "persistence_unavailable"
    assert "commit failure sentinel" not in response.text
    assert len(provider.requests) == 1
    assert row_counts(phase2_engine) == (0, 0)
