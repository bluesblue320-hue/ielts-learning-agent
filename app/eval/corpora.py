"""Repository-safe loaders for the two frozen Phase 10 corpora."""

import json
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from app.eval.schemas import (
    CALIBRATION_CORPUS_VERSION,
    REGRESSION_CORPUS_VERSION,
    CalibrationCase,
    EvalSchema,
    RegressionCase,
)


class CalibrationReferenceDataStatus(StrEnum):
    AVAILABLE = "available"
    NO_ADMISSIBLE_REFERENCE_DATA = "no_admissible_reference_data"


class RegressionCorpus(EvalSchema):
    corpus_version: Literal["writing-eval-regression-corpus-v1"] = (
        REGRESSION_CORPUS_VERSION
    )
    cases: tuple[RegressionCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def has_unique_case_ids(self) -> "RegressionCorpus":
        _require_unique_case_ids(self.cases)
        return self


class CalibrationCorpus(EvalSchema):
    corpus_version: Literal["writing-score-calibration-corpus-v1"] = (
        CALIBRATION_CORPUS_VERSION
    )
    cases: tuple[CalibrationCase, ...] = ()
    reference_data_status: CalibrationReferenceDataStatus

    @model_validator(mode="after")
    def cases_match_reference_data_status(self) -> "CalibrationCorpus":
        _require_unique_case_ids(self.cases)
        if self.cases and self.reference_data_status != CalibrationReferenceDataStatus.AVAILABLE:
            raise ValueError("Calibration cases require available admissible reference data.")
        if not self.cases and self.reference_data_status == CalibrationReferenceDataStatus.AVAILABLE:
            raise ValueError("Available calibration reference data requires at least one case.")
        return self


def _require_unique_case_ids(cases: tuple[RegressionCase | CalibrationCase, ...]) -> None:
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Corpus contains duplicate case IDs.")


def _read_json(path: Path) -> object:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def load_regression_corpus(path: Path, *, fixture_directory: Path) -> RegressionCorpus:
    """Load a strict corpus and prove every declared provider fixture resolves."""

    corpus = RegressionCorpus.model_validate(_read_json(path))
    for case in corpus.cases:
        if case.provider_fixture is not None and not (fixture_directory / case.provider_fixture).is_file():
            raise ValueError(f"Regression case {case.case_id} references unknown fixture {case.provider_fixture}.")
    return corpus


def load_calibration_corpus(path: Path) -> CalibrationCorpus:
    """Load calibration evidence without converting it into regression truth."""

    return CalibrationCorpus.model_validate(_read_json(path))


__all__ = [
    "CalibrationCorpus",
    "CalibrationReferenceDataStatus",
    "RegressionCorpus",
    "load_calibration_corpus",
    "load_regression_corpus",
]
