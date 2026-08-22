"""Concise, source-backed static Writing Task 2 Knowledge snapshot v1."""

from __future__ import annotations

from typing import Final

from app.knowledge.sources import KNOWLEDGE_SOURCES
from app.schemas.knowledge import (
    KNOWLEDGE_VERSION,
    KnowledgeCategory,
    KnowledgeSourceRef,
    KnowledgeUnit,
    WritingTask2TaskType,
)


_CRITERIA: Final[tuple[tuple[str, str], ...]] = (
    ("task_response", "Task Response"),
    ("coherence_and_cohesion", "Coherence and Cohesion"),
    ("lexical_resource", "Lexical Resource"),
    ("grammatical_range_and_accuracy", "Grammatical Range and Accuracy"),
)

_BAND_SUMMARIES: Final[dict[str, tuple[str, ...]]] = {
    "task_response": (
        "No assessable task response is present.",
        "Isolated or copied material gives no answer or position.",
        "The topic is barely engaged; no usable position or developed ideas.",
        "Few task requirements are covered; position and support stay unclear.",
        "Task coverage is partial; the position is weak and support limited.",
        "Main requirements are covered, but position or support is uneven.",
        "Main parts are answered with a relevant position and developed support.",
        "All task parts are answered with a clear position and relevant support.",
        "Thorough task coverage supports a well-developed position and extended ideas.",
        "Every task demand is answered precisely with a fully developed position.",
    ),
    "coherence_and_cohesion": (
        "No assessable organization or connected progression is present.",
        "Isolated language has no progression, paragraphing, or cohesion.",
        "Ideas show almost no logical relationship or organizational control.",
        "Organization, progression, referencing, and cohesion are often unclear.",
        "Some organization exists, but progression or cohesion is unreliable.",
        "Progression is recognizable; paragraphing or cohesion can be mechanical.",
        "Ideas progress coherently in logical paragraphs despite some cohesive lapses.",
        "Logical paragraphing gives clear progression and controlled cohesion.",
        "Skillful sequencing and paragraphing use flexible, unobtrusive cohesion.",
        "Progression, paragraphing, referencing, and cohesion are fully controlled.",
    ),
    "lexical_resource": (
        "No assessable vocabulary is present.",
        "Only isolated words or copied vocabulary can be recognized.",
        "Vocabulary is too limited to sustain meaning.",
        "A narrow range causes imprecision, spelling, and word-formation failures.",
        "Basic vocabulary conveys meaning, but repetition and errors limit precision.",
        "Range is adequate, though word choice or formation errors are noticeable.",
        "Vocabulary is varied and appropriate, with some imprecision or collocation error.",
        "Flexible vocabulary is precise; less-common words and collocation are controlled.",
        "Wide, precise vocabulary is fluent, with only rare formation or spelling slips.",
        "Vocabulary is consistently natural, sophisticated, precise, and controlled.",
    ),
    "grammatical_range_and_accuracy": (
        "No assessable sentence structure is present.",
        "Isolated fragments show almost no grammar or punctuation control.",
        "Minimal structures and errors prevent sustained communication.",
        "Simple forms and frequent grammar or punctuation errors obscure meaning.",
        "Limited structural range and frequent errors disrupt communication.",
        "Simple forms exceed complex-form control; meaning survives frequent errors.",
        "Simple and complex forms are used; errors rarely block meaning.",
        "Varied complex structures show good grammatical and punctuation control.",
        "Wide, flexible structures make most sentences accurate, with rare slips.",
        "A full, natural structural range has consistently accurate control.",
    ),
}


def _descriptor_units() -> tuple[KnowledgeUnit, ...]:
    items: list[KnowledgeUnit] = []
    for criterion, label in _CRITERIA:
        for band, progress in enumerate(_BAND_SUMMARIES[criterion]):
            items.append(
                KnowledgeUnit(
                    knowledge_id=f"writing-{criterion.replace('_', '-')}-band-{band}",
                    category=KnowledgeCategory.BAND_GUIDANCE,
                    criterion=criterion,
                    descriptor_band=band,
                    statement=progress,
                    source_refs=(
                        KnowledgeSourceRef(
                            source_id="ielts-writing-band-descriptors-2023",
                            locator=f"Writing Task 2 / {label} / Band {band}",
                            section=label,
                        ),
                    ),
                )
            )
    return tuple(items)


_CRITERION_UNITS: Final[tuple[KnowledgeUnit, ...]] = tuple(
    KnowledgeUnit(
        knowledge_id=f"writing-{criterion.replace('_', '-')}-criterion",
        category=KnowledgeCategory.ASSESSMENT,
        criterion=criterion,
        statement=f"{label} is one of the four official IELTS Writing Task 2 assessment criteria.",
        source_refs=(
            KnowledgeSourceRef(
                source_id="ielts-writing-key-assessment-criteria",
                locator=f"Writing Task 2 / {label}",
                section=label,
            ),
        ),
    )
    for criterion, label in _CRITERIA
)

_RULE_UNITS: Final[tuple[KnowledgeUnit, ...]] = (
    KnowledgeUnit(
        knowledge_id="writing-task2-minimum-250-words",
        category=KnowledgeCategory.TASK_RULE,
        statement="Writing Task 2 requires an essay of at least 250 words.",
        source_refs=(KnowledgeSourceRef(source_id="ielts-academic-writing-format", locator="Writing Task 2 / format", section="Writing Task 2"),),
    ),
    KnowledgeUnit(
        knowledge_id="writing-task2-connected-text",
        category=KnowledgeCategory.TASK_RULE,
        statement="Task 2 responses are written as full connected text, not notes or bullet points.",
        source_refs=(KnowledgeSourceRef(source_id="ielts-writing-key-assessment-criteria", locator="Writing Task 2 / connected text", section="Writing Task 2"),),
    ),
    KnowledgeUnit(
        knowledge_id="writing-task2-answer-prompt-directly",
        category=KnowledgeCategory.TASK_RULE,
        statement="Read the prompt closely and answer every required part directly and relevantly.",
        source_refs=(KnowledgeSourceRef(source_id="ielts-writing-task2-question-prompts-2023", locator="Advice / read and answer the prompt", section="Advice"),),
    ),
)

_TASK_TYPES: Final[tuple[tuple[WritingTask2TaskType, str], ...]] = (
    (WritingTask2TaskType.OPINION, "State and support a position that answers the opinion prompt."),
    (WritingTask2TaskType.DISCUSSION, "Discuss the requested views and give the requested opinion."),
    (WritingTask2TaskType.MULTI_PART, "Answer each distinct part of the prompt."),
    (WritingTask2TaskType.MULTI_PART_OPINION, "Answer each part and make the required evaluative position clear."),
    (WritingTask2TaskType.ADVANTAGE_DISADVANTAGE, "Address both advantages and disadvantages asked by the prompt."),
    (WritingTask2TaskType.POSITIVE_NEGATIVE, "Evaluate whether the development is positive or negative as asked."),
    (WritingTask2TaskType.CAUSE_SOLUTION, "Explain the requested causes and propose relevant solutions."),
)

_TASK_TYPE_UNITS: Final[tuple[KnowledgeUnit, ...]] = tuple(
    KnowledgeUnit(
        knowledge_id=f"writing-task2-type-{task_type.value.replace('_', '-')}",
        category=KnowledgeCategory.TASK_UNDERSTANDING,
        task_type=task_type,
        statement=statement,
        source_refs=(KnowledgeSourceRef(source_id="ielts-writing-task2-question-prompts-2023", locator=f"Task 2 question types / {task_type.value}", section="Task 2 question types"),),
    )
    for task_type, statement in _TASK_TYPES
)

WRITING_TASK2_KNOWLEDGE_UNITS: Final[tuple[KnowledgeUnit, ...]] = (
    _CRITERION_UNITS + _descriptor_units() + _RULE_UNITS + _TASK_TYPE_UNITS
)


def validate_snapshot_integrity() -> None:
    """Fail closed if the checked-in snapshot violates its provenance contract."""
    identifiers = [unit.knowledge_id for unit in WRITING_TASK2_KNOWLEDGE_UNITS]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Knowledge IDs must be unique")
    for unit in WRITING_TASK2_KNOWLEDGE_UNITS:
        if unit.knowledge_version != KNOWLEDGE_VERSION:
            raise ValueError("Knowledge version mismatch")
        for reference in unit.source_refs:
            if reference.source_id not in KNOWLEDGE_SOURCES:
                raise ValueError(f"Unknown Knowledge source: {reference.source_id}")


validate_snapshot_integrity()
