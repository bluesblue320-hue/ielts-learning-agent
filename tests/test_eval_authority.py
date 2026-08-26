"""P10-08 VETO and fail-closed authority evaluator coverage."""

import pytest

from app.eval.authority import AuthorityEvidence, evaluate_authority
from app.eval.schemas import EvalFinding, EvalResult, EvalSeverity, EvalStatus, EvaluatorId


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"authoritative_operation_succeeded": False, "reported_success": True}, "fabricated_success_after_authoritative_failure"),
        ({"application_owns_product_band": False}, "score_authority_bypass"),
        ({"learner_state_authority_preserved": False}, "learner_state_authority_bypass"),
        ({"learner_owner_matches": False}, "wrong_learner_ownership"),
        ({"episode_owner_matches": False}, "wrong_episode_ownership"),
        ({"recommendation_owner_matches": False}, "wrong_recommendation_ownership"),
        ({"knowledge_provenance_known": False}, "unknown_knowledge_provenance"),
        ({"deterministic_replay": False}, "deterministic_replay_violation"),
        ({"isolated_mutable_data": False}, "non_isolated_mutable_data_access"),
        ({"case_valid": False}, "malformed_case_not_fail_closed"),
    ],
)
def test_every_frozen_authority_violation_is_veto(override: dict[str, bool], code: str) -> None:
    finding = evaluate_authority(AuthorityEvidence(**{"authoritative_operation_succeeded": True, "reported_success": True, **override}))

    assert finding.status == EvalStatus.FAIL
    assert finding.severity == EvalSeverity.VETO
    assert finding.failure_codes == (code,)


def test_authority_passes_only_when_all_frozen_evidence_is_safe() -> None:
    finding = evaluate_authority(AuthorityEvidence(authoritative_operation_succeeded=True, reported_success=True))

    assert finding.status == EvalStatus.PASS


def test_veto_cannot_be_hidden_by_other_passing_evaluators() -> None:
    veto = evaluate_authority(AuthorityEvidence(authoritative_operation_succeeded=False, reported_success=True))
    result = EvalResult(
        run_id="authority-run",
        case_id="authority-case",
        mode="deterministic_regression",
        findings=(
            EvalFinding(evaluator=EvaluatorId.OUTCOME, status=EvalStatus.PASS, severity=EvalSeverity.INFO),
            veto,
        ),
    )

    assert result.status == EvalStatus.FAIL
    assert result.severity == EvalSeverity.VETO
