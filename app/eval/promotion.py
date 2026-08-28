"""Deliberate, provenance-backed regression-case promotion workflow."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from app.eval.schemas import EvalSchema, FailureBoundary, RegressionCase


class PromotionReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PromotionProvenance(EvalSchema):
    failure_boundary: FailureBoundary
    failure_code: str = Field(min_length=1)
    origin: str = Field(min_length=1)
    issue_or_commit_reference: str = Field(min_length=1)
    reproduction_locator: str = Field(min_length=1)


class RegressionPromotionProposal(EvalSchema):
    proposal_version: Literal["writing-eval-regression-promotion-v1"] = (
        "writing-eval-regression-promotion-v1"
    )
    case: RegressionCase
    reason_for_promotion: str = Field(min_length=1)
    contract_basis: Literal["frozen_application_contract"]
    provenance: PromotionProvenance
    provider_dependent: bool = False
    provider_behavior_version: str | None = None
    reproduction_verified: bool
    before_fix_failure_proven: bool
    after_fix_pass_proven: bool
    review_status: PromotionReviewStatus

    @model_validator(mode="after")
    def provider_and_contract_evidence_are_complete(self) -> "RegressionPromotionProposal":
        if self.provenance.failure_boundary is FailureBoundary.CALIBRATION:
            raise ValueError("Calibration disagreement is not a deterministic regression basis.")
        if self.provider_dependent and not (
            self.case.provider_fixture or self.case.captured_fixture_reference
        ):
            raise ValueError("Provider-dependent promotion requires a frozen fixture or capture.")
        if self.provider_dependent and not self.provider_behavior_version:
            raise ValueError("Provider-dependent promotion requires versioned behavior evidence.")
        _reject_unsafe_payload(self.case.model_dump(mode="json"))
        return self


class PromotionDecision(EvalSchema):
    accepted: bool
    case: RegressionCase | None = None
    reason: str


def evaluate_promotion(
    proposal: RegressionPromotionProposal,
    *,
    existing_case_ids: frozenset[str],
    fixture_directory: Path,
) -> PromotionDecision:
    """Validate one proposal without mutating or writing the canonical corpus."""

    if proposal.review_status is not PromotionReviewStatus.APPROVED:
        return PromotionDecision(accepted=False, reason="promotion_review_not_approved")
    if proposal.case.case_id in existing_case_ids:
        return PromotionDecision(accepted=False, reason="duplicate_canonical_case_id")
    if not proposal.reproduction_verified:
        return PromotionDecision(accepted=False, reason="reproduction_not_verified")
    if not proposal.before_fix_failure_proven:
        return PromotionDecision(accepted=False, reason="before_fix_failure_not_proven")
    if not proposal.after_fix_pass_proven:
        return PromotionDecision(accepted=False, reason="after_fix_pass_not_proven")
    fixture = proposal.case.provider_fixture
    if fixture is not None and not (fixture_directory / fixture).is_file():
        return PromotionDecision(accepted=False, reason="provider_fixture_unresolved")
    return PromotionDecision(
        accepted=True,
        case=proposal.case,
        reason="approved_for_manual_corpus_update",
    )


def _reject_unsafe_payload(value: object) -> None:
    forbidden_keys = {
        "api_key",
        "apikey",
        "secret",
        "password",
        "database_url",
        "chain_of_thought",
        "reasoning",
        "python",
        "script",
        "callable",
        "exec",
        "eval",
    }
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = key.lower().replace("-", "_")
            if normalized in forbidden_keys:
                raise ValueError(f"Promotion payload contains forbidden field: {key}")
            _reject_unsafe_payload(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_unsafe_payload(nested)


__all__ = [
    "PromotionDecision",
    "PromotionProvenance",
    "PromotionReviewStatus",
    "RegressionPromotionProposal",
    "evaluate_promotion",
]
