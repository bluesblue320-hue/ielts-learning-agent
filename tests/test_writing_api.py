"""End-to-end HTTP tests for the P2-09 writing evaluation route."""

from collections.abc import Generator
from contextlib import contextmanager
from decimal import Decimal
import inspect

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

import app.api.routes.writing as writing_routes
from app.api.dependencies.writing import get_writing_provider
from app.db.session import create_db_engine, create_session_factory, get_db_session
from app.llm import (
    DeepSeekProvider,
    ProviderError,
    ProviderErrorCategory,
    ProviderErrorContext,
)
from app.main import create_app
from app.models import WritingAttempt, WritingEvaluation
from app.services.writing_persistence import WritingPersistenceError
from tests.fakes import FakeProvider


pytestmark = pytest.mark.integration


def provider_payload(value: str = "6.5") -> dict[str, object]:
    criterion = {
        "band": {"value": value},
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
            "provider": "provider-controlled",
            "model": "provider-controlled",
            "prompt_version": "provider-controlled",
        },
    }


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


@contextmanager
def client_for(
    engine: Engine,
    provider: FakeProvider,
) -> Generator[TestClient, None, None]:
    session_factory = create_session_factory(engine)

    def session_override() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_writing_provider] = lambda: provider
    app.dependency_overrides[get_db_session] = session_override
    with TestClient(app) as client:
        yield client


def row_counts(engine: Engine) -> tuple[int, int]:
    factory = create_session_factory(engine)
    with factory() as session:
        return (
            session.scalar(select(func.count()).select_from(WritingAttempt)) or 0,
            session.scalar(select(func.count()).select_from(WritingEvaluation)) or 0,
        )


def test_valid_request_evaluates_persists_and_returns_explicit_schema(
    writing_engine: Engine,
) -> None:
    provider = FakeProvider([provider_payload()])
    with client_for(writing_engine, provider) as http:
        response = http.post(
            "/writing/evaluate",
            json={
                "question": "Discuss both views.",
                "essay": "A short but valid response.",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["attempt_id"] == 1
    assert body["evaluation"]["word_count"] == 5
    assert body["evaluation"]["product_band"] == {"value": "6.5"}
    assert body["evaluation"]["metadata"] == {
        "provider": "fake-provider",
        "model": "fake-model",
        "prompt_version": "writing-v1",
    }
    assert len(provider.requests) == 1
    assert row_counts(writing_engine) == (1, 1)

    factory = create_session_factory(writing_engine)
    with factory() as session:
        attempt = session.scalar(select(WritingAttempt))
        evaluation = session.scalar(select(WritingEvaluation))
        assert attempt is not None
        assert evaluation is not None
        assert attempt.question == "Discuss both views."
        assert attempt.essay == "A short but valid response."
        assert attempt.word_count == 5
        assert evaluation.attempt_id == attempt.id
        assert evaluation.product_band == Decimal("6.5")


@pytest.mark.parametrize(
    "payload",
    [
        {"question": " ", "essay": "A valid essay."},
        {"question": "A valid question.", "essay": "\t\n"},
    ],
)
def test_blank_input_returns_422_without_provider_or_write(
    writing_engine: Engine,
    payload: dict[str, str],
) -> None:
    provider = FakeProvider([provider_payload()])
    with client_for(writing_engine, provider) as client:
        response = client.post("/writing/evaluate", json=payload)

    assert response.status_code == 422
    assert provider.requests == []
    assert row_counts(writing_engine) == (0, 0)


def test_below_250_word_essay_is_accepted(writing_engine: Engine) -> None:
    provider = FakeProvider([provider_payload()])
    with client_for(writing_engine, provider) as client:
        response = client.post(
            "/writing/evaluate",
            json={"question": "Why?", "essay": "Only four words here."},
        )

    assert response.status_code == 201
    assert response.json()["evaluation"]["word_count"] == 4
    assert row_counts(writing_engine) == (1, 1)


def test_provider_failure_returns_safe_error_without_write(
    writing_engine: Engine,
) -> None:
    failure = ProviderError(
        ProviderErrorCategory.TIMEOUT,
        "vendor detail that must not leak",
        context=ProviderErrorContext(provider="fake-provider"),
    )
    provider = FakeProvider([failure])
    with client_for(writing_engine, provider) as client:
        response = client.post(
            "/writing/evaluate",
            json={"question": "Why?", "essay": "A valid response."},
        )

    assert response.status_code == 502
    assert response.json() == {"detail": "Writing evaluation provider failed."}
    assert "vendor detail" not in response.text
    assert row_counts(writing_engine) == (0, 0)


def test_persistence_failure_returns_safe_error_without_write(
    writing_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingPersistenceService:
        def __init__(self, session: Session) -> None:
            self._session = session

        def persist(self, submission: object, evaluation: object) -> None:
            raise WritingPersistenceError("private database detail")

    monkeypatch.setattr(
        writing_routes,
        "WritingEvaluationPersistenceService",
        FailingPersistenceService,
    )
    provider = FakeProvider([provider_payload()])
    with client_for(writing_engine, provider) as client:
        response = client.post(
            "/writing/evaluate",
            json={"question": "Why?", "essay": "A valid response."},
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Writing evaluation could not be persisted."
    }
    assert "private database detail" not in response.text
    assert row_counts(writing_engine) == (0, 0)


def test_production_composition_ignores_fake_provider_environment_selector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IELTS_PROVIDER", "fake")
    monkeypatch.setenv("IELTS_DEEPSEEK_API_KEY", "test-placeholder-not-a-secret")

    provider = get_writing_provider()

    assert isinstance(provider, DeepSeekProvider)
    assert provider.provider_name == "deepseek"


def test_route_remains_thin_and_openapi_declares_response_schema() -> None:
    app = create_app()
    operation = app.openapi()["paths"]["/writing/evaluate"]["post"]
    route_source = inspect.getsource(writing_routes.evaluate_writing)

    assert operation["responses"]["201"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/WritingEvaluationResponse"}
    assert "WritingEvaluationService" in route_source
    assert "WritingEvaluationPersistenceService" in route_source
    assert "aggregate_product_band" not in route_source
    assert "WRITING_RUBRIC" not in route_source
