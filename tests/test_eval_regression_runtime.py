"""Official canonical regression runtime coverage and PostgreSQL proof."""

import inspect
import os

import pytest
from sqlalchemy import create_engine, func, select

from app.eval.corpora import load_regression_corpus
from app.eval.regression_runtime import (
    CANONICAL_FIXTURE_ROOT,
    CanonicalRegistryError,
    CanonicalRegressionRuntime,
    execute_canonical_regression,
    validate_canonical_executor_registry,
)
from app.eval.schemas import EvalStatus
from app.models.learning import LearningUpdate
from app.models.practice import WritingPractice
from app.models.writing import WritingAttempt


def _corpus():
    return load_regression_corpus(
        CANONICAL_FIXTURE_ROOT / "regression_corpus.json",
        fixture_directory=CANONICAL_FIXTURE_ROOT,
    )


def test_official_registry_exactly_covers_canonical_case_ids() -> None:
    corpus = _corpus()
    runtime = CanonicalRegressionRuntime(factory=object())  # type: ignore[arg-type]

    registry = runtime.executors(corpus)

    assert set(registry) == {case.case_id for case in corpus.cases}
    source = inspect.getsource(
        __import__("app.eval.regression_runtime", fromlist=["*"])
    )
    assert "_passing_executor" not in source


def test_registry_fails_closed_for_missing_unknown_and_duplicate_ids() -> None:
    corpus = _corpus()

    def executor(_case):
        return ()

    complete = tuple((case.case_id, executor) for case in corpus.cases)

    with pytest.raises(CanonicalRegistryError, match="missing"):
        validate_canonical_executor_registry(corpus, complete[:-1])
    with pytest.raises(CanonicalRegistryError, match="unknown"):
        validate_canonical_executor_registry(
            corpus, (*complete, ("unknown-case", executor))
        )
    with pytest.raises(CanonicalRegistryError, match="duplicate"):
        validate_canonical_executor_registry(corpus, (*complete, complete[0]))


@pytest.mark.integration
def test_canonical_runtime_executes_every_case_with_real_evaluators_and_reports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("IELTS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("IELTS_TEST_DATABASE_URL is required for PostgreSQL integration")
    corpus = _corpus()
    calls: set[str] = set()
    import app.eval.regression_runtime as runtime_module

    for function_name in (
        "evaluate_outcome",
        "evaluate_trajectory",
        "evaluate_knowledge_grounding",
        "evaluate_authority",
        "evaluate_lifecycle",
    ):
        original = getattr(runtime_module, function_name)

        def tracked(*args, _name=function_name, _original=original, **kwargs):
            calls.add(_name)
            return _original(*args, **kwargs)

        monkeypatch.setattr(runtime_module, function_name, tracked)

    first = execute_canonical_regression(
        run_id="canonical-runtime-repeatability",
        database_url=database_url,
    )
    second = execute_canonical_regression(
        run_id="canonical-runtime-repeatability",
        database_url=database_url,
    )

    expected_ids = {case.case_id for case in corpus.cases}
    assert len(corpus.cases) == 11
    assert len(first.suite.cases) == len(corpus.cases)
    assert {case.case_id for case in first.suite.cases} == expected_ids
    assert first.suite.status is EvalStatus.PASS
    assert all(case.status is EvalStatus.PASS for case in first.suite.cases)
    assert tuple(
        (case.case_id, case.status, case.findings) for case in first.suite.cases
    ) == tuple(
        (case.case_id, case.status, case.findings) for case in second.suite.cases
    )
    cases_by_id = {case.case_id: case for case in first.suite.cases}
    for case in corpus.cases:
        executed = {finding.evaluator for finding in cases_by_id[case.case_id].findings}
        assert set(case.applicable_evaluators).issubset(executed)
    assert calls == {
        "evaluate_outcome",
        "evaluate_trajectory",
        "evaluate_knowledge_grounding",
        "evaluate_authority",
        "evaluate_lifecycle",
    }
    assert first.structured_report.suite_status is EvalStatus.PASS
    assert first.structured_report.summary.case_count == len(corpus.cases)
    assert "Suite status: `pass`" in first.human_report

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert (
                connection.scalar(select(func.count()).select_from(WritingAttempt)) == 0
            )
            assert (
                connection.scalar(select(func.count()).select_from(LearningUpdate)) == 0
            )
            assert (
                connection.scalar(select(func.count()).select_from(WritingPractice))
                == 0
            )
    finally:
        engine.dispose()


@pytest.mark.integration
def test_real_canonical_executor_failure_cannot_be_overridden_by_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("IELTS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("IELTS_TEST_DATABASE_URL is required for PostgreSQL integration")
    import app.eval.regression_runtime as runtime_module
    from app.eval.schemas import EvalFinding, EvalSeverity, EvaluatorId, FailureBoundary

    original = runtime_module.evaluate_outcome

    def fail_product_band(case, observed):
        if case.case_id == "product-band-application-authority":
            return EvalFinding(
                evaluator=EvaluatorId.OUTCOME,
                status=EvalStatus.FAIL,
                severity=EvalSeverity.VETO,
                first_failing_boundary=FailureBoundary.EVALUATION,
                failure_codes=("forced_real_evaluator_failure",),
            )
        return original(case, observed)

    monkeypatch.setattr(runtime_module, "evaluate_outcome", fail_product_band)
    execution = execute_canonical_regression(
        run_id="canonical-runtime-no-synthetic-pass",
        database_url=database_url,
    )

    assert execution.suite.status is EvalStatus.FAIL
    failed = next(
        case
        for case in execution.suite.cases
        if case.case_id == "product-band-application-authority"
    )
    assert failed.status is EvalStatus.FAIL
