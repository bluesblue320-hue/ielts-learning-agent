"""Test-only FastAPI server for Phase 5/6 browser E2E."""
import os
from alembic import command
from alembic.config import Config
import uvicorn
from app.api.dependencies.practice import get_practice_generator
from app.api.dependencies.writing import get_writing_provider
from app.db.session import create_db_engine, create_session_factory, get_db_session
from app.main import create_app
from tests.fakes import FakePracticeGenerator, FakeProvider


def payload() -> dict[str, object]:
    """Deterministic evaluation payload.

    All payloads use the same task_response band (6.0) so that the total
    number of evaluations per learner never changes the longitudinal trend:
    three observations of 6.0 yield trend=stable and persistent_gap=true
    against a 7.0 target. The provider is scripted with identical payloads, so
    the result is independent of which spec consumed earlier payloads.
    """
    base = {"band": {"value": "6.5"}, "evidence": ["Relevant evidence."], "feedback": "Develop this criterion."}
    task_response = {"band": {"value": "6.0"}, "evidence": ["Position is clear but support stays general."], "feedback": "Develop specific examples for your position."}
    return {
        "criteria": {
            "task_response": task_response,
            "coherence_and_cohesion": base,
            "lexical_resource": base,
            "grammatical_range_and_accuracy": base,
        },
        "strengths": ["Clear position."],
        "weaknesses": ["Support remains general."],
        "error_tags": [],
        "recommended_skills": ["supporting examples"],
        "feedback": "Use more precise evidence.",
    }


def main() -> None:
    url = os.environ["IELTS_E2E_DATABASE_URL"]
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    factory = create_session_factory(create_db_engine(url))

    def session_override():
        with factory() as session:
            yield session

    application = create_app()
    application.dependency_overrides[get_db_session] = session_override
    # Scripted identical payloads: enough for every spec's evaluations without
    # depending on which spec ran first.
    application.dependency_overrides[get_writing_provider] = lambda: FakeProvider([payload() for _ in range(20)])
    application.dependency_overrides[get_practice_generator] = lambda: FakePracticeGenerator()
    uvicorn.run(application, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()