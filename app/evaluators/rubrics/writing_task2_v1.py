"""Product-safe summarized IELTS Writing Task 2 rubric, version 1."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from app.schemas.writing import WritingCriterion


WRITING_TASK2_RUBRIC_VERSION: Final[str] = "writing-task2-v1"
WRITING_TASK2_MINIMUM_WORDS: Final[int] = 250

WRITING_TASK2_CRITERION_DEFINITIONS: Final[Mapping[WritingCriterion, str]] = (
    MappingProxyType(
        {
            WritingCriterion.TASK_RESPONSE: (
                "How fully and relevantly the response answers every part of the "
                "task, maintains a position, and develops supported ideas."
            ),
            WritingCriterion.COHERENCE_AND_COHESION: (
                "How clearly ideas progress and are organized into paragraphs, "
                "with controlled referencing and cohesive devices."
            ),
            WritingCriterion.LEXICAL_RESOURCE: (
                "The range, precision, appropriacy, spelling, and word-formation "
                "control of vocabulary used to express the response."
            ),
            WritingCriterion.GRAMMATICAL_RANGE_AND_ACCURACY: (
                "The range and flexibility of sentence structures together with "
                "grammatical and punctuation accuracy."
            ),
        }
    )
)

_TASK_RESPONSE = {
    "0": "No assessable response is present.",
    "1": "Only isolated or copied material is present; the task is not answered.",
    "2": "A barely recognizable response touches the topic without a usable position.",
    "3": "Few task requirements are addressed; ideas and position are unclear or minimal.",
    "4": "The task is only partly answered; a position is unclear and support is limited.",
    "5": "Main requirements are generally addressed, but the position or support is uneven.",
    "6": "Main parts are addressed with a relevant position and generally developed support.",
    "7": "All parts are addressed with a clear position and relevant, developed support.",
    "8": "The task is handled thoroughly with a well-developed position and extended support.",
    "9": "The response addresses the task precisely with a fully developed, convincing position.",
}
_COHERENCE_AND_COHESION = {
    "0": "No assessable organization is present.",
    "1": "Isolated language has no discernible progression or cohesion.",
    "2": "Ideas are extremely limited and relationships between them are largely absent.",
    "3": "Organization is weak; progression and referencing are frequently unclear.",
    "4": "Some organization exists, but progression, paragraphing, or cohesion is unreliable.",
    "5": "There is recognizable progression, with mechanical or inaccurate cohesion and paragraphs.",
    "6": "Ideas progress coherently overall; paragraphing is logical despite some lapses.",
    "7": "Information is logically organized with clear progression and controlled cohesion.",
    "8": "Sequencing and paragraphing are skillful; cohesion is flexible and rarely distracting.",
    "9": "Progression is effortless and fully controlled throughout the response.",
}
_LEXICAL_RESOURCE = {
    "0": "No assessable vocabulary is present.",
    "1": "Only isolated words or copied language can be recognized.",
    "2": "Vocabulary is extremely limited and cannot communicate sustained meaning.",
    "3": "A very limited range causes frequent imprecision and spelling or formation breakdowns.",
    "4": "Basic vocabulary conveys some meaning but repetition and error restrict precision.",
    "5": "The range is adequate for the topic, though word choice and formation errors are noticeable.",
    "6": "Vocabulary is sufficiently varied and generally appropriate, with some imprecision.",
    "7": "A flexible range conveys precise meaning; less common language is mostly well controlled.",
    "8": "Wide, precise vocabulary is used fluently with only rare non-systematic slips.",
    "9": "Vocabulary control is consistently natural, precise, and sophisticated.",
}
_GRAMMATICAL_RANGE_AND_ACCURACY = {
    "0": "No assessable sentence structure is present.",
    "1": "Only isolated fragments are produced with almost no grammatical control.",
    "2": "Structures are extremely limited and errors prevent sustained communication.",
    "3": "Only simple forms are attempted; frequent errors substantially obscure meaning.",
    "4": "A limited structural range communicates basic meaning with frequent errors.",
    "5": "Simple forms are controlled better than complex ones; errors remain frequent but meaning survives.",
    "6": "A mix of simple and complex forms is used; errors occur but rarely block meaning.",
    "7": "A variety of complex structures is used with good control and few meaning-affecting errors.",
    "8": "Structures are wide and flexible; most sentences are accurate with rare slips.",
    "9": "A full structural range is used naturally with consistently accurate control.",
}

WRITING_TASK2_BAND_DESCRIPTORS: Final[
    Mapping[WritingCriterion, Mapping[str, str]]
] = MappingProxyType(
    {
        WritingCriterion.TASK_RESPONSE: MappingProxyType(_TASK_RESPONSE),
        WritingCriterion.COHERENCE_AND_COHESION: MappingProxyType(
            _COHERENCE_AND_COHESION
        ),
        WritingCriterion.LEXICAL_RESOURCE: MappingProxyType(_LEXICAL_RESOURCE),
        WritingCriterion.GRAMMATICAL_RANGE_AND_ACCURACY: MappingProxyType(
            _GRAMMATICAL_RANGE_AND_ACCURACY
        ),
    }
)

WRITING_TASK2_HALF_BAND_GUIDANCE: Final[str] = (
    "Use a half band only when performance consistently exceeds the lower integer "
    "descriptor but does not yet satisfy the next integer descriptor overall."
)
WRITING_TASK2_LENGTH_GUIDANCE: Final[str] = (
    "Task 2 requires at least 250 words. This API accepts shorter essays, but the "
    "application-supplied word count is evaluation evidence: insufficient length "
    "may limit task development and should affect only criteria justified by the "
    "descriptors, never trigger request rejection by the evaluator."
)


def writing_task2_band_descriptors() -> dict[WritingCriterion, dict[str, str]]:
    """Return a mutable transport copy without exposing rubric globals."""

    return {
        criterion: dict(descriptors)
        for criterion, descriptors in WRITING_TASK2_BAND_DESCRIPTORS.items()
    }
