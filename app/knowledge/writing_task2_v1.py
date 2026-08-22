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
        'No genuine attempt, English response, or original content is present.',
        'At 20 words or fewer, content is unrelated or copied.',
        'Barely prompt-related; no position and almost no developed ideas.',
        'Prompt misunderstood; no position and few relevant ideas.',
        'Minimal/tangential response; position and support are hard to find.',
        'Incomplete coverage; unclear position and underdeveloped ideas.',
        'Uneven coverage; relevant position or support may lack clarity.',
        'Main task parts covered; clear position; support may lack focus.',
        'Prompt sufficiently addressed; position and support developed.',
        'In-depth response; developed position and well-supported ideas.',
    ),
    "coherence_and_cohesion": (
        'No genuine response to assess organization or cohesion.',
        'At 20 words or fewer, no communicative organization is evident.',
        'Little control of organization is evident.',
        'No logical organization; ideas barely connect; paragraphs fail.',
        'No clear progression; basic links misfire and topics stay unclear.',
        'Some coherence, but weak links; paragraphing may be missing.',
        'Clear progression; mechanical cohesion or illogical paragraphs.',
        'Progression is logical; cohesion has lapses; paragraphing works.',
        'Easy logical flow; cohesion and paragraphing are well managed.',
        'Effortless flow, unobtrusive cohesion, skilful paragraphs.',
    ),
    "lexical_resource": (
        'No genuine response is available to assess vocabulary.',
        'At 20 words or fewer, only isolated words are evident.',
        'Extremely few recognisable strings; no spelling or word-formation control.',
        'Inadequate or memorised vocabulary; errors often block meaning.',
        'Basic, repetitive, unsuitable vocabulary; errors may block meaning.',
        'Limited, minimally adequate range; errors may hinder reading.',
        'Adequate but restricted or imprecise; errors do not block meaning.',
        'Some vocabulary flexibility; less-common words/collocation have lapses.',
        'Wide, fluent, precise range; uncommon usage may have occasional lapses.',
        'Wide, natural, precise vocabulary; errors are rare.',
    ),
    "grammatical_range_and_accuracy": (
        'No genuine response is available to assess sentence control.',
        'At 20 words or fewer, no rateable grammar is evident.',
        'Almost no sentence forms appear beyond memorised language.',
        'Grammar/punctuation errors dominate and block most meaning.',
        'Very limited simple forms; frequent errors may impede meaning.',
        'Limited repetitive forms; faulty complex attempts hinder reading.',
        'Simple/complex forms are inflexible; errors rarely block meaning.',
        'Complex structures vary; grammatical/punctuation control is good.',
        'Wide, flexible forms; most sentences are accurate.',
        'Wide, controlled range; errors are extremely rare.',
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
