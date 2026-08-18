"""P4-03 writing practice generation policy consistency tests.

Static/documentation contract tests for the frozen
`writing-practice-generation-v1` policy. No Phase 4 runtime code exists at
this node; phrase matching normalizes whitespace.
"""

import pathlib
import re

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = PROJECT_ROOT / "docs" / "WRITING_PRACTICE_GENERATION_POLICY.md"
CONTRACT = PROJECT_ROOT / "docs" / "WRITING_PRACTICE_PRODUCT_CONTRACT.md"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _text(path: pathlib.Path) -> str:
    return _normalize(path.read_text(encoding="utf-8"))


def test_policy_document_and_version_frozen() -> None:
    policy = _text(POLICY)
    assert "writing-practice-generation-v1" in policy
    assert "PracticeRecommendation controls WHAT" in policy
    assert "PracticeGenerator controls HOW" in policy


def test_llm_never_chooses_authority_fields() -> None:
    policy = _text(POLICY)
    for forbidden in (
        "target_skill",
        "learner target",
        "planner reason",
        "planner version",
        "decision type",
        "learner state",
    ):
        assert forbidden in policy
    assert "MUST NOT choose" in policy


def test_decision_gating_frozen() -> None:
    policy = _text(POLICY)
    assert "decision_type = practice" in policy
    assert "decision_type = no_practice" in policy
    assert "zero generator calls" in policy
    assert "zero `writing_practices` rows" in policy


def test_task2_only_and_supported_skills() -> None:
    policy = _text(POLICY)
    assert "Writing Task 2 ONLY" in policy
    for skill in (
        "task_response",
        "coherence_and_cohesion",
        "lexical_resource",
        "grammatical_range_and_accuracy",
    ):
        assert skill in policy


def test_structured_output_and_maximum_sizes() -> None:
    policy = _text(POLICY)
    assert "question" in policy and "400 characters" in policy
    assert "focus_objective" in policy and "300 characters" in policy
    assert "instructions" in policy and "200 characters" in policy
    assert "checkpoints" in policy and "200 characters" in policy


def test_authority_mirroring_validation_frozen() -> None:
    policy = _text(POLICY)
    assert "MUST equal the persisted recommendation" in policy
    assert "invalid provider response" in policy
    assert "no row" in policy


def test_success_only_persistence_frozen() -> None:
    policy = _text(POLICY)
    assert "SUCCESS-ONLY" in policy
    assert "no `writing_practices` row" in policy
    assert "no failed-generation status or error-category row" in policy


def test_idempotency_and_concurrency_limitation_frozen() -> None:
    policy = _text(POLICY)
    assert "at most one durable" in policy
    assert "UNIQUE(recommendation_id)" in policy
    assert "Exactly-once provider invocation is NOT guaranteed" in policy


def test_retry_wrapper_architecture_frozen() -> None:
    policy = _text(POLICY)
    assert "RetryingPracticeGenerator" in policy
    assert "NOT the evaluator-specific `RetryingProvider` directly" in policy


def test_consistency_with_product_contract() -> None:
    contract = _text(CONTRACT)
    policy = _text(POLICY)
    for phrase in ("cold_start", "no_practice", "decision_type = practice"):
        assert phrase in policy and phrase in contract
    assert "writing-practice-product-v1" in contract
    assert "writing-practice-generation-v1" in policy
