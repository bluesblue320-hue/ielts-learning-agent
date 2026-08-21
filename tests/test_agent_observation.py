"""Focused P8-05 provider-free Agent observation tests."""

from types import SimpleNamespace

import pytest

from app.agent.observation import observe_agent_state
from app.schemas.agent import NoPracticeReason, ObservationKind
from app.schemas.practice import PracticeLifecycleState
from app.services.learning_application import LearnerNotFoundError


class StubSession:
    def __init__(self, values: list[object], *, learner: object | None = object()) -> None:
        self._values = iter(values)
        self.learner = learner
        self.statements: list[object] = []

    def get(self, _model, _identifier):
        return self.learner

    def scalar(self, statement):
        self.statements.append(statement)
        return next(self._values)


def _recommendation(*, decision_type: str = "practice", reasons: list[str] | None = None):
    return SimpleNamespace(
        id=31,
        decision_type=decision_type,
        reason_codes=reasons or ["largest_target_gap"],
    )


def test_no_updates_needs_initial_writing_without_provider() -> None:
    session = StubSession([None])

    state = observe_agent_state(session, learner_id=7)

    assert state.observation.kind == ObservationKind.NEEDS_INITIAL_WRITING
    assert state.latest_learning_update_id is None
    assert len(session.statements) == 1
    assert "ORDER BY learning_updates.id DESC" in str(session.statements[0])


def test_no_practice_preserves_the_full_frozen_reason_sequence(monkeypatch) -> None:
    recommendation = _recommendation(
        decision_type="no_practice",
        reasons=["target_achieved", "insufficient_evidence"],
    )
    monkeypatch.setattr(
        "app.agent.observation.reconstruct_persisted_decision",
        lambda _row: "safe-decision",
    )
    session = StubSession([SimpleNamespace(id=12), recommendation])

    state = observe_agent_state(session, learner_id=7)

    assert state.observation.kind == ObservationKind.NO_PRACTICE
    assert state.observation.no_practice_reason_codes == [
        NoPracticeReason.TARGET_ACHIEVED,
        NoPracticeReason.INSUFFICIENT_EVIDENCE,
    ]
    assert state.recommendation == "safe-decision"
    assert state.practice is None


def test_practice_without_durable_row_needs_generation(monkeypatch) -> None:
    recommendation = _recommendation()
    monkeypatch.setattr(
        "app.agent.observation.reconstruct_persisted_decision",
        lambda _row: "safe-decision",
    )
    session = StubSession([SimpleNamespace(id=12), recommendation, None])

    state = observe_agent_state(session, learner_id=7)

    assert state.observation.kind == ObservationKind.NEEDS_GENERATION
    assert state.recommendation_id == 31
    assert state.practice_id is None


@pytest.mark.parametrize(
    ("lifecycle", "expected"),
    [
        (PracticeLifecycleState.GENERATED.value, ObservationKind.NEEDS_PRACTICE_SUBMISSION),
        (PracticeLifecycleState.SUBMISSION_IN_PROGRESS.value, ObservationKind.AWAIT_SUBMISSION),
    ],
)
def test_existing_nonfinal_practice_is_classified_without_provider(
    monkeypatch, lifecycle: str, expected: ObservationKind
) -> None:
    recommendation = _recommendation()
    practice = SimpleNamespace(
        id=45,
        lifecycle_state=lifecycle,
        submission_fingerprint="opaque-fingerprint",
    )
    monkeypatch.setattr(
        "app.agent.observation.reconstruct_persisted_decision",
        lambda _row: "safe-decision",
    )
    monkeypatch.setattr(
        "app.agent.observation.practice_response",
        lambda _row: "safe-practice",
    )
    session = StubSession([SimpleNamespace(id=12), recommendation, practice])

    state = observe_agent_state(session, learner_id=7)

    assert state.observation.kind == expected
    assert state.practice == "safe-practice"
    assert state.practice_submission_fingerprint == "opaque-fingerprint"


def test_unknown_learner_is_not_silently_classified() -> None:
    with pytest.raises(LearnerNotFoundError):
        observe_agent_state(StubSession([], learner=None), learner_id=7)
