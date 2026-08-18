"""Test-only FastAPI server for Phase 5 browser E2E."""
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
    criterion = {"band": {"value": "6.5"}, "evidence": ["Relevant evidence."], "feedback": "Develop this criterion."}
    return {"criteria": {"task_response": criterion, "coherence_and_cohesion": criterion, "lexical_resource": criterion, "grammatical_range_and_accuracy": criterion}, "strengths": ["Clear position."], "weaknesses": ["Support remains general."], "error_tags": [], "recommended_skills": ["supporting examples"], "feedback": "Use more precise evidence."}


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
    application.dependency_overrides[get_writing_provider] = lambda: FakeProvider([payload(), payload()])
    application.dependency_overrides[get_practice_generator] = lambda: FakePracticeGenerator()
    uvicorn.run(application, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()