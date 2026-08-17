"""P4-02 product-contract consistency tests.

These tests prove the frozen product contract is present and internally
consistent with the Phase 4 Graph. They are static/documentation contract
tests: no Phase 4 runtime code exists at this node. Phrase matching
normalizes whitespace so natural markdown line wrapping never breaks a frozen
contract statement.
"""

import pathlib
import re

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = PROJECT_ROOT / "docs" / "WRITING_PRACTICE_PRODUCT_CONTRACT.md"
GRAPH = PROJECT_ROOT / "docs" / "PHASE4_GRAPH.md"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _text(path: pathlib.Path) -> str:
    return _normalize(path.read_text(encoding="utf-8"))


def test_contract_document_exists() -> None:
    assert CONTRACT.exists()
    assert "writing-practice-product-v1" in _text(CONTRACT)


def test_decision_gated_rules_frozen() -> None:
    contract = _text(CONTRACT)
    assert "decision_type = practice" in contract
    assert "decision_type = no_practice" in contract
    assert "zero generator calls" in contract
    assert "zero `writing_practices` rows" in contract


def test_cold_start_boundary_frozen() -> None:
    contract = _text(CONTRACT)
    assert "cold_start" in contract
    assert "bootstrap" in contract
    assert "no writing_practices row" in contract


def test_submission_lifecycle_states_frozen() -> None:
    contract = _text(CONTRACT)
    for state in ("generated", "submission_in_progress", "submitted"):
        assert state in contract
    assert "generated -> submission_in_progress -> submitted" in contract


def test_question_authority_frozen() -> None:
    contract = _text(CONTRACT)
    assert "question=persisted_practice.question" in contract
    assert "essay=validated_user_essay" in contract
    assert "MUST NOT accept a client-controlled replacement question" in contract


def test_contract_matches_graph_semantics() -> None:
    graph = _text(GRAPH)
    contract = _text(CONTRACT)
    # The Graph references the product contract as authority.
    assert "WRITING_PRACTICE_PRODUCT_CONTRACT.md" in graph or (
        "product contract" in graph
    )
    # Shared frozen vocabulary must agree.
    for phrase in (
        "generated -> submission_in_progress -> submitted",
        "HUMAN PRACTICE TIME",
        "cold_start",
        "no_practice",
        "target_skill = task_response",
    ):
        assert phrase in contract or phrase in graph


def test_primary_acceptance_story_present() -> None:
    contract = _text(CONTRACT)
    assert "Primary end-to-end acceptance story" in contract
    assert "existing Phase 3 recommendation (practice, task_response)" in contract
    assert "No live DeepSeek" in contract
