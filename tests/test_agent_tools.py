"""P8-06 direct Agent tool-boundary tests."""

import asyncio

from app.agent.tools import AgentTools


class Generation:
    async def generate_or_resolve_current(self, **kwargs):
        self.kwargs = kwargs
        return "generation"


class Submission:
    async def submit(self, **kwargs):
        self.kwargs = kwargs
        return "submission"


class Completion:
    def complete(self, **kwargs):
        self.kwargs = kwargs
        return "completion"


def test_tools_delegate_directly_to_existing_services() -> None:
    generation = Generation()
    submission = Submission()
    completion = Completion()
    tools = AgentTools(
        generation=generation,
        submission=submission,
        completion=completion,
    )

    assert asyncio.run(
        tools.generate_practice(
            learner_id=1, recommendation_id=2, expected_learning_update_id=3
        )
    ) == "generation"
    assert asyncio.run(
        tools.submit_practice(learner_id=1, practice_id=4, essay="Essay.")
    ) == "submission"
    assert tools.complete_practice(learner_id=1, practice_id=4) == "completion"
    assert generation.kwargs == {
        "learner_id": 1,
        "recommendation_id": 2,
        "expected_learning_update_id": 3,
    }
    assert submission.kwargs["learner_id"] == 1
    assert submission.kwargs["practice_id"] == 4
    assert submission.kwargs["submission"].essay == "Essay."
    assert completion.kwargs == {"learner_id": 1, "practice_id": 4}
