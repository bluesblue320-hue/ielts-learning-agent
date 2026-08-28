"""P10-14 deliberate regression-promotion validation tests."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.eval.promotion import RegressionPromotionProposal, evaluate_promotion
from app.eval.schemas import RegressionCase


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "eval"


def _case(**overrides: object) -> RegressionCase:
    values: dict[str, object] = {
        "case_id": "promoted-contract-regression",
        "description": "A stable authority contract regression reproduction.",
        "category": "authority",
        "input": {"authority_state": "provider_attempted_override"},
        "expected_structured_outcomes": {"reported_success": False},
        "applicable_evaluators": ("authority",),
        "severity_expectations": ({"boundary": "authority", "severity": "veto"},),
        "provenance": {
            "source": "reviewed-regression",
            "locator": "tests/test_eval_promotion.py",
        },
    }
    values.update(overrides)
    return RegressionCase.model_validate(values)


def _proposal(**overrides: object) -> RegressionPromotionProposal:
    values: dict[str, object] = {
        "case": _case(),
        "reason_for_promotion": "Protect the stable authority boundary, not an implementation detail.",
        "contract_basis": "frozen_application_contract",
        "provenance": {
            "failure_boundary": "authority",
            "failure_code": "authority_bypass",
            "origin": "reviewed issue reproduction",
            "issue_or_commit_reference": "issue-123/commit-abc",
            "reproduction_locator": "tests/test_eval_promotion.py::test_approved_proposal",
        },
        "reproduction_verified": True,
        "before_fix_failure_proven": True,
        "after_fix_pass_proven": True,
        "review_status": "approved",
    }
    values.update(overrides)
    return RegressionPromotionProposal.model_validate(values)


def test_approved_proposal_is_returned_for_manual_corpus_update_only() -> None:
    decision = evaluate_promotion(
        _proposal(),
        existing_case_ids=frozenset(),
        fixture_directory=FIXTURE_ROOT,
    )

    assert decision.accepted is True
    assert decision.case is not None
    assert decision.reason == "approved_for_manual_corpus_update"


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"review_status": "pending"}, "promotion_review_not_approved"),
        ({"reproduction_verified": False}, "reproduction_not_verified"),
        ({"before_fix_failure_proven": False}, "before_fix_failure_not_proven"),
        ({"after_fix_pass_proven": False}, "after_fix_pass_not_proven"),
    ],
)
def test_unreviewed_or_unproven_proposals_are_rejected(override, reason: str) -> None:
    decision = evaluate_promotion(
        _proposal(**override),
        existing_case_ids=frozenset(),
        fixture_directory=FIXTURE_ROOT,
    )
    assert decision.accepted is False
    assert decision.reason == reason


def test_duplicate_case_id_is_rejected_without_writing_corpus() -> None:
    proposal = _proposal()
    decision = evaluate_promotion(
        proposal,
        existing_case_ids=frozenset({proposal.case.case_id}),
        fixture_directory=FIXTURE_ROOT,
    )
    assert decision.reason == "duplicate_canonical_case_id"


def test_provider_dependent_promotion_requires_versioned_resolvable_fixture() -> None:
    with pytest.raises(ValidationError, match="frozen fixture or capture"):
        _proposal(provider_dependent=True, provider_behavior_version="provider-v1")
    with pytest.raises(ValidationError, match="versioned behavior"):
        _proposal(
            provider_dependent=True,
            case=_case(provider_fixture="provider-valid-payload.json"),
        )
    decision = evaluate_promotion(
        _proposal(
            provider_dependent=True,
            provider_behavior_version="provider-v1",
            case=_case(provider_fixture="not-present.json"),
        ),
        existing_case_ids=frozenset(),
        fixture_directory=FIXTURE_ROOT,
    )
    assert decision.reason == "provider_fixture_unresolved"


def test_calibration_disagreement_and_unsafe_payloads_cannot_be_promoted() -> None:
    with pytest.raises(ValidationError, match="Calibration disagreement"):
        _proposal(
            provenance={
                "failure_boundary": "calibration",
                "failure_code": "reference_score_disagreement",
                "origin": "calibration observation",
                "issue_or_commit_reference": "calibration-run-1",
                "reproduction_locator": "capture-1",
            }
        )
    with pytest.raises(ValidationError, match="forbidden field"):
        _proposal(case=_case(input={"script": "arbitrary python"}))
    with pytest.raises(ValidationError, match="forbidden field"):
        _proposal(case=_case(input={"api_key": "must-never-enter-corpus"}))
