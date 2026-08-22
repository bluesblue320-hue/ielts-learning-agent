"""Reviewed semantic compatibility ledger for the frozen Writing Task 2 rubric."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from types import MappingProxyType
from typing import Final, Mapping, Sequence

from app.evaluators.rubrics.writing_task2_v1 import WRITING_TASK2_BAND_DESCRIPTORS
from app.knowledge.writing_task2_v1 import WRITING_TASK2_KNOWLEDGE_UNITS
from app.schemas.knowledge import KnowledgeCategory
from app.schemas.writing import WritingCriterion


class RubricCompatibilityStatus(StrEnum):
    COMPATIBLE = "compatible"
    COMPATIBLE_WITH_MISSING_PROVENANCE = "compatible_with_missing_provenance"
    GAP_REQUIRES_DOCUMENTATION = "gap_requires_documentation"
    MATERIAL_CONFLICT = "material_conflict"


@dataclass(frozen=True, slots=True)
class RubricCompatibilityEntry:
    criterion: WritingCriterion
    band: int
    rubric_anchor_sha256: str
    knowledge_ids: tuple[str, ...]
    knowledge_statement_sha256: str
    compatibility_status: RubricCompatibilityStatus
    rationale: str


_TR = WritingCriterion.TASK_RESPONSE
_CC = WritingCriterion.COHERENCE_AND_COHESION
_LR = WritingCriterion.LEXICAL_RESOURCE
_GRA = WritingCriterion.GRAMMATICAL_RANGE_AND_ACCURACY
_MISSING = RubricCompatibilityStatus.COMPATIBLE_WITH_MISSING_PROVENANCE


def _entry(
    criterion: WritingCriterion,
    band: int,
    rubric_hash: str,
    knowledge_id: str,
    knowledge_hash: str,
    status: RubricCompatibilityStatus,
    rationale: str,
) -> RubricCompatibilityEntry:
    return RubricCompatibilityEntry(
        criterion=criterion,
        band=band,
        rubric_anchor_sha256=rubric_hash,
        knowledge_ids=(knowledge_id,),
        knowledge_statement_sha256=knowledge_hash,
        compatibility_status=status,
        rationale=rationale,
    )


# Every row explicitly records the reviewed criterion/band, both immutable text
# identities, mapped Knowledge ID, decision, and rationale. An ID resolving by
# itself therefore cannot establish compatibility.
RUBRIC_COMPATIBILITY_LEDGER: Final[tuple[RubricCompatibilityEntry, ...]] = (
    _entry(_TR, 0, "feeccd2e2799efa5e5e224a7256e80efef4e8ba26c225c9638d719ed4ecdca46", "writing-task-response-band-0", "d535523d001142329e1c2bb473ac065569797f12e015e6c5296573598bfff39c", _MISSING, "Both anchors require an assessable task response; the v1 rubric has no claim-level source record."),
    _entry(_TR, 1, "5689317fb0a57a280d437673efa3d3ab96f5c89be9a799580934d2e23915a650", "writing-task-response-band-1", "dcbe3620b029f55b9834d30bfb22c0b623078611fbcaed3ab85c2d4f6f7d4ec1", _MISSING, "Both anchors describe isolated or copied material without a task answer or position; v1 provenance is absent."),
    _entry(_TR, 2, "bcb508920d277fdf0a34951bd9f273e0f587181bf732e8ce4f65c59e5fd0b2df", "writing-task-response-band-2", "8ef0a8f3cc4e3a41bb1abe5503a1fa0e933b274d7ee1491799631115a12c7da4", _MISSING, "Both anchors describe barely engaging the topic without a usable position or developed ideas; v1 provenance is absent."),
    _entry(_TR, 3, "cd74d41ae84b349fb6ac47237c7b3fb1646b1678d0652cc753e5284a0eb1fdb3", "writing-task-response-band-3", "62a86aa83c4a73ab2d9d0a8b4b2da4da892f8ee300a18618accf4da92542dc83", _MISSING, "Both anchors describe few task requirements, an unclear position, and minimal support; v1 provenance is absent."),
    _entry(_TR, 4, "0e6b33693e9097db7cdef867f86fafbf9e6a6321a5a1bc5c81d30a12d5ef9af4", "writing-task-response-band-4", "85f086b5f53e1b5cb2ae6e9e8fc45ceb0b38333dff4f6bec33f59cf82720f3b3", _MISSING, "Both anchors describe partial task coverage, a weak or unclear position, and limited support; v1 provenance is absent."),
    _entry(_TR, 5, "0c6ff172fe30c4176f486efd565d97c7f2af0f59b1c273a7a259a6e231c9798b", "writing-task-response-band-5", "2545549c8ff22e6767be992c2e59382a919d9d4f2fbcab81e859410812ae291f", _MISSING, "Both anchors describe generally covering main requirements with uneven position or support; v1 provenance is absent."),
    _entry(_TR, 6, "c56b890b113bec5122a963cd47f6c1973bc371b01a65dfce14f8cd08e22cbc11", "writing-task-response-band-6", "2bdc9ed3f4968dae779aae2f577e94541e9dba18b72575216101bb2fbce81716", _MISSING, "Both anchors describe addressing main parts with a relevant position and generally developed support; v1 provenance is absent."),
    _entry(_TR, 7, "49afca87946c6a2f00eb7e6113fdd00de7b6ec97f2bf0a97d89dc35f1dc9fb35", "writing-task-response-band-7", "bed4c35f34d29144110c9112ca8cba2340a8e47084f1a0a73603d98cdee26213", _MISSING, "Both anchors require all task parts, a clear position, and relevant developed support; v1 provenance is absent."),
    _entry(_TR, 8, "cb8d5aa1d6acd1d6423a3b64113ce3a2109d316d54bcbf7c306a5681f2d09c6d", "writing-task-response-band-8", "1d584dfe9e20c7c11d4cc3bc86e0445957ce369c2c34e9adb51067dacaeb8821", _MISSING, "Both anchors describe thorough task handling, a well-developed position, and extended support; v1 provenance is absent."),
    _entry(_TR, 9, "c6b9338c76a70d79e79f2c026fb9077f8a89479881cd0b7bbb4e47240a09334d", "writing-task-response-band-9", "aeb9199d9ecb343630c79272177605ef716b2a793bf1d555b8b32713b7425ad7", _MISSING, "Both anchors describe precise task coverage through a fully developed and convincing position; v1 provenance is absent."),
    _entry(_CC, 0, "4700db78cff96700e995ed4822ff8b3ee23af1333b8c21fc2cd1a9b34e98a97f", "writing-coherence-and-cohesion-band-0", "9b3f2ca787265b9b9da7b7bc8dbf7f669e0031d83886f38851808f185b4a8753", _MISSING, "Both anchors require assessable organization or connected progression; the v1 rubric lacks claim provenance."),
    _entry(_CC, 1, "176b92e129a59520daf1d198f945e10af7c7d9e007e10eccc0de00266d0fad0c", "writing-coherence-and-cohesion-band-1", "8299eb7c41bd5339f7232042bbd5851c82fe25b1ae81064dce8b5959a102b0e9", _MISSING, "Both anchors describe isolated language without discernible progression or cohesion; v1 provenance is absent."),
    _entry(_CC, 2, "468c4b75023964c32201c4795155d3ee536b875527fceb0211e366f8d9dd2788", "writing-coherence-and-cohesion-band-2", "fd43968d72d13e75d0febc386b8acd4aaf681789cb6394ad46c0edec1b4f090a", _MISSING, "Both anchors describe very limited ideas with relationships and organization largely absent; v1 provenance is absent."),
    _entry(_CC, 3, "68be671b852af5753776ac965df6e5a0c2617b8e9e6012107e21569210632619", "writing-coherence-and-cohesion-band-3", "89269409830f458a52103018f9b08eed404e8f7c0393246fb75d1afc1df94ad9", _MISSING, "Both anchors describe weak organization, progression, referencing, and cohesion; v1 provenance is absent."),
    _entry(_CC, 4, "ce426568e0a696e449fb7946711c17ffd3e997ad4812c342d396937b6909f80f", "writing-coherence-and-cohesion-band-4", "9849fc7d16e9e80cd9f603a3a6705ec917c1a6f3a9b55c4f60aab80b3c33cac4", _MISSING, "Both anchors describe some organization with unreliable progression, paragraphing, or cohesion; v1 provenance is absent."),
    _entry(_CC, 5, "bec53e05c0cb8fa77bd9b01d768d38448adc5cdc7968884aa6006602fc55aa5d", "writing-coherence-and-cohesion-band-5", "626141ef40c3560f7b5dfe397aa38b96153d0d5b8e3fa74a6f83b94f03fe8da5", _MISSING, "Both anchors describe recognizable progression with mechanical cohesion or paragraphing; v1 provenance is absent."),
    _entry(_CC, 6, "0ed8019bb0c1ddc80fb868b52b818392d95e046c08f484595da1994f9b7cfa7a", "writing-coherence-and-cohesion-band-6", "d8de1faacf1158f023e24497b6458eb66b6a284a9a8c1ab65f84d71250bc1437", _MISSING, "Both anchors describe coherent overall progression and logical paragraphing with some lapses; v1 provenance is absent."),
    _entry(_CC, 7, "9aa68bc035690ce70c0eb3892d057d27ffbaa53228923d85c56024310c6a8a1a", "writing-coherence-and-cohesion-band-7", "ad0d8e559964ce56ff0e91db3202d98181758a1feef87712b8e3f7236fd9ab47", _MISSING, "Both anchors require logical organization, clear progression, and controlled cohesion; v1 provenance is absent."),
    _entry(_CC, 8, "81871dcbdd30c860ff07a7e291400b484388011c87cfe948e6243ac05f221c6d", "writing-coherence-and-cohesion-band-8", "edb17822540243b40ff345221e4d53c2ef19d1ef4514364caf34c65609b923d3", _MISSING, "Both anchors describe skillful sequencing and paragraphing with flexible unobtrusive cohesion; v1 provenance is absent."),
    _entry(_CC, 9, "2354d9bc0be33e1797fe4c309f64afbfb093d79e5e2450d6957ffff79d555e7d", "writing-coherence-and-cohesion-band-9", "fd238c62556d9bc5935df8b79f956e12a1f10315220fe7165d61cf7e9f2678d5", _MISSING, "Both anchors describe effortless, natural, fully controlled progression and cohesion; v1 provenance is absent."),
    _entry(_LR, 0, "407b681a3ee2bc8ea7d632f46222102078900c2add1c1a332b7bd76b9913b551", "writing-lexical-resource-band-0", "407b681a3ee2bc8ea7d632f46222102078900c2add1c1a332b7bd76b9913b551", _MISSING, "Both anchors require assessable vocabulary; the v1 rubric lacks claim-level source provenance."),
    _entry(_LR, 1, "8b569396c09a42a904f1d23a5aefc66d63cd156bf090f147c760ecf51d0fac85", "writing-lexical-resource-band-1", "8fb36482abb8184f044f5f584e7637ec98c7d09a6328e125a377f279355196f8", _MISSING, "Both anchors describe only isolated words or copied vocabulary; v1 provenance is absent."),
    _entry(_LR, 2, "4ed46629eda281d18993329892e06341a6819318019aca329ca4f6bddac8a9fc", "writing-lexical-resource-band-2", "4b8b8075e9a22a26a93dfcbcd4eb0dc997ff30090bd8ed3bf08437765b4de05d", _MISSING, "Both anchors describe vocabulary too limited to sustain meaning; v1 provenance is absent."),
    _entry(_LR, 3, "10f4ce131dfc14910105082c5a9988e91672d7a5dbfe425b93d8c1b7f6e767f6", "writing-lexical-resource-band-3", "0d85e80563fd52ce6eb40fb57a07c81db714a0e11886d6bcaf829229a99a183c", _MISSING, "Both anchors describe a narrow range causing imprecision, spelling, and word-formation failures; v1 provenance is absent."),
    _entry(_LR, 4, "943c90b45ac49eee7e45d46685bd127dbeff1502c1acc118de79bb99dc5f5f6e", "writing-lexical-resource-band-4", "363e217b3b4a8bc911a10fac3b409b0d3f86e72d8a8bcfdd14b28d014edad645", _MISSING, "Both anchors describe basic vocabulary restricted by repetition and error; v1 provenance is absent."),
    _entry(_LR, 5, "3b6cebc4d99018fd97954251895b23e2a13aa672edcdfcf619ae0c31264d3275", "writing-lexical-resource-band-5", "3e2af0ee118d81dd76034de9dd28f56837251ade8a841818e51d0153766ce8ba", _MISSING, "Both anchors describe adequate range with noticeable word-choice or formation errors; v1 provenance is absent."),
    _entry(_LR, 6, "ff3c9dff291f7fa16a221c70f7c4fda422208c58551ad5b406c4be2035fd3af5", "writing-lexical-resource-band-6", "5fcd0344d10022d933ef00f2a6143ad7bb8bc54a8baa9d2a91d19ed4d0274c9f", _MISSING, "Both anchors describe sufficiently varied, generally appropriate vocabulary with some imprecision; v1 provenance is absent."),
    _entry(_LR, 7, "3cefbbd63b4d9a1288ac7f8d3f7a2d8f6f1487bf77c304dbbdc0bde1a2cd51ac", "writing-lexical-resource-band-7", "fd8532f47a5a8254074f1b5de78827cb0a3d97770273c0663ff63b70502eca0d", _MISSING, "Both anchors require flexible, precise vocabulary and mostly controlled less-common language; v1 provenance is absent."),
    _entry(_LR, 8, "85d9216e9b54dfee7623e51c91d03e5d32bd61ac76ea5c6d770649716ef071cf", "writing-lexical-resource-band-8", "7aa98505b916a1dd9c292fb5abf40a434a2061ee9039d9e2db7aeb5b5f62c05f", _MISSING, "Both anchors describe wide, precise, fluent vocabulary with rare slips; v1 provenance is absent."),
    _entry(_LR, 9, "0d7033fc82c0c9700ab5639fb886b39e20cd29795eaca398ed42891903d8a891", "writing-lexical-resource-band-9", "20832d827a3006c06dd539044ade129dc0e310d3180ac6ccc9bc24b37cdbc8b1", _MISSING, "Both anchors describe consistently natural, precise, sophisticated vocabulary control; v1 provenance is absent."),
    _entry(_GRA, 0, "4c4f5cdc3d783a6539e6d54aa1fa7abf83aedf2724e464a7a51ccbb18e5e091f", "writing-grammatical-range-and-accuracy-band-0", "4c4f5cdc3d783a6539e6d54aa1fa7abf83aedf2724e464a7a51ccbb18e5e091f", _MISSING, "Both anchors require assessable sentence structure; the v1 rubric lacks claim-level source provenance."),
    _entry(_GRA, 1, "953551b41cfd0888136b5212881298fd8354571bee672b9d7fce79904bc86aff", "writing-grammatical-range-and-accuracy-band-1", "4e77b452b498d0a66060e3fb65d761dcc2a20d4381a54df347594688705e996c", _MISSING, "Both anchors describe isolated fragments with almost no grammatical control; v1 provenance is absent."),
    _entry(_GRA, 2, "8c8a8541b827342cec360d086afe487f2e6ec58d42ea557d8dae255cc438117f", "writing-grammatical-range-and-accuracy-band-2", "80b14a9d28f98aa54174ec41a6af01b1c92eac33c9f0cbe43dea71301cd5ece3", _MISSING, "Both anchors describe extremely limited structures whose errors prevent sustained communication; v1 provenance is absent."),
    _entry(_GRA, 3, "61d9a218755bacd1e117ab674a1ae7179dee32aab17d7109ff2605b1fc8d7cf9", "writing-grammatical-range-and-accuracy-band-3", "2e23bf3c7f72f959bbf21fa1a0dc174604c89d1ebaed5731743bda5ad885103c", _MISSING, "Both anchors describe mainly simple forms and frequent errors that obscure meaning; v1 provenance is absent."),
    _entry(_GRA, 4, "a4d2735d7fdd29fa7614af3b8aa073dbe5815eb6aaf9dab696c3245f383daec3", "writing-grammatical-range-and-accuracy-band-4", "385ffd86999edf914f1a61f1628365841db516d5d1b99d42ca26b14c46f635b7", _MISSING, "Both anchors describe limited structural range with frequent disruptive errors; v1 provenance is absent."),
    _entry(_GRA, 5, "797251a5d3ef91bf3b0ada363b4534bb20b8b62251c23b40c547ac5f7003b9c9", "writing-grammatical-range-and-accuracy-band-5", "547d3c4fb86db6304eec7a302c94d45fd47fa91cd5b4f633c06eb290b9a34598", _MISSING, "Both anchors describe stronger simple than complex forms, with frequent errors but retained meaning; v1 provenance is absent."),
    _entry(_GRA, 6, "6b29cae4f4c012f85f481f2f6e3d36a00048422f78b86524b8763bd99a4df750", "writing-grammatical-range-and-accuracy-band-6", "d253fc31ae10c00b108fe69e40fe6fb3dca4e333b0387085158faa14c484c187", _MISSING, "Both anchors describe a mix of simple and complex forms whose errors rarely block meaning; v1 provenance is absent."),
    _entry(_GRA, 7, "fc5601425c42d65e7269117850aa680c082e8182241126fe15873d11e52169df", "writing-grammatical-range-and-accuracy-band-7", "a74a8eeb3608e3c891390fc0c5cc537b777ee172bb0602f887f81e0549887a7b", _MISSING, "Both anchors require varied complex structures with good grammatical control and few meaning-affecting errors; v1 provenance is absent."),
    _entry(_GRA, 8, "0dd75b69f53fc51d9281747367b9de9c074faf2b7028bd7c1998ee3662908fa1", "writing-grammatical-range-and-accuracy-band-8", "e67e1cf251d45b8b749bb26df7127e3b0ea61b3cb8d8261d41bd4fc76783deb6", _MISSING, "Both anchors describe wide, flexible structures with mostly accurate sentences and rare slips; v1 provenance is absent."),
    _entry(_GRA, 9, "5bd7dd3b685489b55c21bcba738a84d40f9b13711c57df93124102d0cb9e3c83", "writing-grammatical-range-and-accuracy-band-9", "2e4a5ce0db78e9d93a14bf1cf8f08da4ee1301b256d0a5e00a0edfcc4b2dbfa8", _MISSING, "Both anchors describe a full, natural structural range with consistently accurate control; v1 provenance is absent."),
)


def _text_sha256(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def validate_rubric_compatibility_ledger(
    ledger: Sequence[RubricCompatibilityEntry] = RUBRIC_COMPATIBILITY_LEDGER,
) -> None:
    """Fail closed unless the reviewed ledger exactly matches both frozen inputs."""

    expected_keys = {(criterion, band) for criterion in WritingCriterion for band in range(10)}
    if len(ledger) != len(expected_keys):
        raise ValueError("rubric compatibility ledger must contain exactly 40 entries")
    snapshot = {unit.knowledge_id: unit for unit in WRITING_TASK2_KNOWLEDGE_UNITS}
    seen: set[tuple[WritingCriterion, int]] = set()
    for entry in ledger:
        if not isinstance(entry, RubricCompatibilityEntry):
            raise ValueError("rubric compatibility ledger contains an invalid entry")
        if not isinstance(entry.criterion, WritingCriterion) or type(entry.band) is not int:
            raise ValueError("rubric compatibility ledger has an invalid criterion or band")
        key = (entry.criterion, entry.band)
        if key in seen:
            raise ValueError("rubric compatibility ledger contains a duplicate entry")
        seen.add(key)
        if key not in expected_keys:
            raise ValueError("rubric compatibility ledger contains an unexpected entry")
        if not isinstance(entry.compatibility_status, RubricCompatibilityStatus):
            raise ValueError("rubric compatibility ledger has an invalid status")
        if not isinstance(entry.rationale, str) or not entry.rationale.strip():
            raise ValueError("rubric compatibility ledger rationale is required")
        if not entry.knowledge_ids or len(set(entry.knowledge_ids)) != len(entry.knowledge_ids):
            raise ValueError("rubric compatibility ledger knowledge references are invalid")

        rubric_text = WRITING_TASK2_BAND_DESCRIPTORS[entry.criterion][str(entry.band)]
        if _text_sha256(rubric_text) != entry.rubric_anchor_sha256:
            raise ValueError("frozen rubric wording differs from the reviewed semantic anchor")
        units = []
        for knowledge_id in entry.knowledge_ids:
            unit = snapshot.get(knowledge_id)
            if unit is None:
                raise ValueError("rubric compatibility Knowledge reference does not resolve")
            if (
                unit.category is not KnowledgeCategory.BAND_GUIDANCE
                or unit.criterion != entry.criterion.value
                or unit.descriptor_band != entry.band
            ):
                raise ValueError("rubric compatibility Knowledge dimensions do not align")
            units.append(unit)
        if _text_sha256("\n".join(unit.statement for unit in units)) != entry.knowledge_statement_sha256:
            raise ValueError("Knowledge wording differs from the reviewed semantic anchor")
    if seen != expected_keys:
        raise ValueError("rubric compatibility ledger is missing a criterion/band entry")


validate_rubric_compatibility_ledger()


RUBRIC_KNOWLEDGE_MAP: Final[Mapping[WritingCriterion, Mapping[int, tuple[str, ...]]]] = MappingProxyType(
    {
        criterion: MappingProxyType(
            {
                entry.band: entry.knowledge_ids
                for entry in RUBRIC_COMPATIBILITY_LEDGER
                if entry.criterion is criterion
            }
        )
        for criterion in WritingCriterion
    }
)


def audit_writing_task2_rubric(
    ledger: Sequence[RubricCompatibilityEntry] = RUBRIC_COMPATIBILITY_LEDGER,
) -> Mapping[WritingCriterion, Mapping[int, RubricCompatibilityStatus]]:
    """Return only statuses declared by the validated semantic ledger."""

    validate_rubric_compatibility_ledger(ledger)
    return MappingProxyType(
        {
            criterion: MappingProxyType(
                {
                    entry.band: entry.compatibility_status
                    for entry in ledger
                    if entry.criterion is criterion
                }
            )
            for criterion in WritingCriterion
        }
    )
