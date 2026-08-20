"""Test-only FastAPI server for Phase 5/6 browser E2E."""
import os
from decimal import Decimal
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
import uvicorn
from app.api.dependencies.practice import get_practice_generator
from app.api.dependencies.writing import get_writing_provider
from app.db.session import create_db_engine, create_session_factory, get_db_session
from app.main import create_app
from app.models.learning import Learner, LearningUpdate, PracticeRecommendation
from app.models.writing import WritingAttempt, WritingEvaluation
from app.services.learning_application import apply_writing_evaluation
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
    @application.post("/e2e/phase7/{planner_version}")
    def seed_phase7_planner(planner_version: str) -> dict[str, int | str]:
        """Create one test-only persisted recommendation for Chromium coverage."""

        if planner_version not in {
            "writing-practice-gap-v1",
            "writing-practice-gap-memory-v2",
        }:
            raise HTTPException(status_code=400, detail="unsupported planner version")

        tied_v2 = planner_version == "writing-practice-gap-memory-v2"
        bands = {
            "task_response": Decimal("6.0"),
            "coherence_and_cohesion": Decimal("6.0") if tied_v2 else Decimal("6.5"),
            "lexical_resource": Decimal("6.5"),
            "grammatical_range_and_accuracy": Decimal("6.5"),
        }
        criteria_feedback = {
            skill: {"evidence": ["Seeded evidence."], "feedback": "Seeded feedback."}
            for skill in bands
        }
        with factory() as session:
            learner = Learner(writing_target_band=Decimal("7.0"))
            session.add(learner)
            session.flush()
            attempt = WritingAttempt(
                question="Seeded Phase 7 browser test question.",
                essay="Seeded browser test essay.",
                word_count=4,
            )
            session.add(attempt)
            session.flush()
            evaluation = WritingEvaluation(
                attempt_id=attempt.id,
                task_response_band=bands["task_response"],
                coherence_and_cohesion_band=bands["coherence_and_cohesion"],
                lexical_resource_band=bands["lexical_resource"],
                grammatical_range_and_accuracy_band=bands[
                    "grammatical_range_and_accuracy"
                ],
                product_band=Decimal("6.5"),
                criteria_feedback=criteria_feedback,
                strengths=["Seeded strength."],
                weaknesses=["Seeded weakness."],
                error_tags=[],
                recommended_skills=[],
                feedback="Seeded overall feedback.",
                provider="e2e-seed",
                model="e2e-seed",
                prompt_version="e2e-seed-v1",
                rubric_version="e2e-seed-v1",
                scoring_policy_version="e2e-seed-v1",
                thinking_mode="disabled",
            )
            session.add(evaluation)
            session.commit()
            result = apply_writing_evaluation(
                session,
                learner_id=learner.id,
                writing_evaluation_id=evaluation.id,
            )
            if planner_version == "writing-practice-gap-v1":
                recommendation = session.get(
                    PracticeRecommendation,
                    result.recommendation_id,
                )
                learning_update = session.get(LearningUpdate, result.learning_update_id)
                assert recommendation is not None and learning_update is not None
                recommendation.planner_version = planner_version
                recommendation.planner_context_snapshot = None
                learning_update.planner_version = planner_version
                session.commit()
            return {
                "learner_id": learner.id,
                "recommendation_id": result.recommendation_id,
                "planner_version": planner_version,
            }
    uvicorn.run(application, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()