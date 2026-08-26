"""P10-04 corpus separation, provenance, and fixture-resolution tests."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.eval.corpora import (
    CalibrationReferenceDataStatus,
    load_calibration_corpus,
    load_regression_corpus,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "eval"


def test_regression_corpus_is_versioned_unique_and_resolves_fixtures() -> None:
    corpus = load_regression_corpus(
        FIXTURE_ROOT / "regression_corpus.json",
        fixture_directory=FIXTURE_ROOT,
    )

    assert corpus.corpus_version == "writing-eval-regression-corpus-v1"
    assert len(corpus.cases) == len({case.case_id for case in corpus.cases})
    assert len(corpus.cases) == 10
    assert {case.category.value for case in corpus.cases} >= {
        "provider_contract",
        "persistence",
        "state",
        "memory",
        "recommendation",
        "practice",
        "knowledge",
        "agent_trajectory",
    }
    planner_tie = next(case for case in corpus.cases if case.case_id == "memory-planner-exact-tie")
    assert planner_tie.expected_structured_outcomes["tie_break_order"] == "persistent_gap_trend_recency_priority"


def test_regression_corpus_rejects_unknown_fixture_reference(tmp_path: Path) -> None:
    data = json.loads((FIXTURE_ROOT / "regression_corpus.json").read_text(encoding="utf-8"))
    data["cases"][0]["provider_fixture"] = "not-present.json"
    path = tmp_path / "regression.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown fixture"):
        load_regression_corpus(path, fixture_directory=FIXTURE_ROOT)


def test_calibration_corpus_truthfully_declares_reference_data_gap() -> None:
    corpus = load_calibration_corpus(FIXTURE_ROOT / "calibration_corpus.json")

    assert corpus.cases == ()
    assert corpus.reference_data_status == CalibrationReferenceDataStatus.NO_ADMISSIBLE_REFERENCE_DATA


def test_calibration_corpus_rejects_cases_without_available_reference_status(tmp_path: Path) -> None:
    data = json.loads((FIXTURE_ROOT / "calibration_corpus.json").read_text(encoding="utf-8"))
    data["cases"] = [
        {
            "case_id": "not-admissible",
            "question": "Discuss both views and give your opinion.",
            "essay": "Repository-only placeholder that must not become reference truth.",
            "reference_labels": [
                {
                    "rater_id": "unsupported",
                    "criteria": {
                        "task_response": {"value": "6.0"},
                        "coherence_and_cohesion": {"value": "6.0"},
                        "lexical_resource": {"value": "6.0"},
                        "grammatical_range_and_accuracy": {"value": "6.0"}
                    },
                    "provenance": {"source": "unsupported", "locator": "unsupported"}
                }
            ],
            "reference_tier": "b",
            "provenance": {"source": "unsupported", "locator": "unsupported"},
            "ambiguity": "unambiguous"
        }
    ]
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValidationError, match="require available admissible reference data"):
        load_calibration_corpus(path)
