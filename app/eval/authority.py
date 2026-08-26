"""Explicit fail-closed authority evaluation for P10-08."""

from pydantic import BaseModel, ConfigDict

from app.eval.schemas import (
    EvalFinding,
    EvalSeverity,
    EvalStatus,
    EvaluatorId,
    FailureBoundary,
)


class AuthorityEvidence(BaseModel):
    """Application-owned evidence flags; Eval never grants production authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authoritative_operation_succeeded: bool
    reported_success: bool
    application_owns_product_band: bool = True
    application_owns_metadata: bool = True
    learner_state_authority_preserved: bool = True
    learner_owner_matches: bool = True
    episode_owner_matches: bool = True
    recommendation_owner_matches: bool = True
    knowledge_provenance_known: bool = True
    deterministic_replay: bool = True
    isolated_mutable_data: bool = True
    case_valid: bool = True


def evaluate_authority(evidence: AuthorityEvidence) -> EvalFinding:
    """Return the first VETO authority violation, or a deterministic pass."""

    checks: tuple[tuple[bool, str], ...] = (
        (
            not evidence.authoritative_operation_succeeded and evidence.reported_success,
            "fabricated_success_after_authoritative_failure",
        ),
        (not evidence.application_owns_product_band, "score_authority_bypass"),
        (not evidence.application_owns_metadata, "application_metadata_authority_bypass"),
        (not evidence.learner_state_authority_preserved, "learner_state_authority_bypass"),
        (not evidence.learner_owner_matches, "wrong_learner_ownership"),
        (not evidence.episode_owner_matches, "wrong_episode_ownership"),
        (not evidence.recommendation_owner_matches, "wrong_recommendation_ownership"),
        (not evidence.knowledge_provenance_known, "unknown_knowledge_provenance"),
        (not evidence.deterministic_replay, "deterministic_replay_violation"),
        (not evidence.isolated_mutable_data, "non_isolated_mutable_data_access"),
        (not evidence.case_valid, "malformed_case_not_fail_closed"),
    )
    for violated, code in checks:
        if violated:
            return EvalFinding(
                evaluator=EvaluatorId.AUTHORITY,
                status=EvalStatus.FAIL,
                severity=EvalSeverity.VETO,
                first_failing_boundary=FailureBoundary.AUTHORITY,
                failure_codes=(code,),
            )
    return EvalFinding(
        evaluator=EvaluatorId.AUTHORITY,
        status=EvalStatus.PASS,
        severity=EvalSeverity.INFO,
    )


__all__ = ["AuthorityEvidence", "evaluate_authority"]
