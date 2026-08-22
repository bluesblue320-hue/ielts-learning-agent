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
_GAP = RubricCompatibilityStatus.GAP_REQUIRES_DOCUMENTATION


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
    _entry(_TR, 0, "feeccd2e2799efa5e5e224a7256e80efef4e8ba26c225c9638d719ed4ecdca46", "writing-task-response-band-0", "5fa5329e9abff4170aa1266377b75aaf060f49eb07531a05f8acd3fb8535b6c5", _MISSING, "Both reserve Band 0 for an unassessable genuine response; v1 lacks the official attempt, language, memorisation, and claim-provenance detail."),
    _entry(_TR, 1, "5689317fb0a57a280d437673efa3d3ab96f5c89be9a799580934d2e23915a650", "writing-task-response-band-1", "087df3f9be6c15135bfccd584232a59c00a66c379fcbc9c57ae2beff39ef2660", _MISSING, "Both describe essentially no usable task answer, including unrelated or copied content; v1 lacks the official word-count and claim provenance."),
    _entry(_TR, 2, "bcb508920d277fdf0a34951bd9f273e0f587181bf732e8ce4f65c59e5fd0b2df", "writing-task-response-band-2", "8dbd5925d8ce22c44f3c543e8f6267c2e7404fd7f31caa9d83ed35a2c47424eb", _MISSING, "Both describe content barely related to the prompt with no position or developed ideas; v1 lacks claim provenance."),
    _entry(_TR, 3, "cd74d41ae84b349fb6ac47237c7b3fb1646b1678d0652cc753e5284a0eb1fdb3", "writing-task-response-band-3", "393f901a156865bc4408e8728271929628456a86a0f2927ce8cfaa928be26ef3", _GAP, "Official Band 3 has no adequately addressed prompt part or identifiable position; v1's few-addressed-requirements anchor is meaningfully less severe."),
    _entry(_TR, 4, "0e6b33693e9097db7cdef867f86fafbf9e6a6321a5a1bc5c81d30a12d5ef9af4", "writing-task-response-band-4", "388fe542585fe32b0f75aaa708e6c328b12f8435436080cf54353132f868111d", _GAP, "Official Band 4 is minimal or tangential and makes position and supported ideas hard to identify; v1's partly-answered wording overstates fulfilment."),
    _entry(_TR, 5, "0c6ff172fe30c4176f486efd565d97c7f2af0f59b1c273a7a259a6e231c9798b", "writing-task-response-band-5", "f7cdca14a3bb4194846fc3ae9441baf3cbd4b3dbcb13aa567fb7a6ad8759ca33", _GAP, "Official Band 5 requires incomplete prompt coverage, unclear position development, and limited ideas; v1 says main requirements are generally addressed."),
    _entry(_TR, 6, "c56b890b113bec5122a963cd47f6c1973bc371b01a65dfce14f8cd08e22cbc11", "writing-task-response-band-6", "daf48b6f99fe1b3eeb85036b87f67d8b2f434d0591a814fd18aa6203353547ff", _GAP, "Official Band 6 permits uneven coverage, unclear conclusions, and inadequate support; v1's generally-developed-support wording is stronger."),
    _entry(_TR, 7, "49afca87946c6a2f00eb7e6113fdd00de7b6ec97f2bf0a97d89dc35f1dc9fb35", "writing-task-response-band-7", "ab31055186c8747feee4929604fd3bf41f89a2b81af707f99bb5224daa800ce9", _GAP, "Official Band 7 covers main parts but permits over-generalised or unfocused support; v1's all-parts and developed-support anchor is stronger."),
    _entry(_TR, 8, "cb8d5aa1d6acd1d6423a3b64113ce3a2109d316d54bcbf7c306a5681f2d09c6d", "writing-task-response-band-8", "139a5edc7b1eccdf03743ab681720171984e3c488852d2600c27952ef969d438", _GAP, "Official Band 8 requires sufficient appropriate coverage with occasional lapses; v1's thorough and extended wording is closer to Band 9 severity."),
    _entry(_TR, 9, "c6b9338c76a70d79e79f2c026fb9077f8a89479881cd0b7bbb4e47240a09334d", "writing-task-response-band-9", "17293429e498ad78387879c16976075c4489524752a1e4b58f5acd55513d050a", _MISSING, "Both require an in-depth answer, fully developed position, and relevant well-supported ideas; v1 lacks claim provenance."),
    _entry(_CC, 0, "4700db78cff96700e995ed4822ff8b3ee23af1333b8c21fc2cd1a9b34e98a97f", "writing-coherence-and-cohesion-band-0", "b3d519812958c77b92d1965d7628b38dfe777b4ce453e39fc86dd32e01d2f083", _MISSING, "Both leave no genuine response from which organization or cohesion can be assessed; v1 lacks the official Band 0 conditions and claim provenance."),
    _entry(_CC, 1, "176b92e129a59520daf1d198f945e10af7c7d9e007e10eccc0de00266d0fad0c", "writing-coherence-and-cohesion-band-1", "c3b883b57fa9ac5fe4f05ffcc3e0599cc84669b983d1f29f2ebdde588eb870cc", _MISSING, "Both describe no communicative organization or progression; v1 lacks the official word-count condition and claim provenance."),
    _entry(_CC, 2, "468c4b75023964c32201c4795155d3ee536b875527fceb0211e366f8d9dd2788", "writing-coherence-and-cohesion-band-2", "cdec33371f095e6241de30865a4ef9b75ede8b986f86b89eec6dcd9d46efdc08", _MISSING, "Both describe little evidence of organizational control; v1 lacks claim provenance."),
    _entry(_CC, 3, "68be671b852af5753776ac965df6e5a0c2617b8e9e6012107e21569210632619", "writing-coherence-and-cohesion-band-3", "01040db33a276ade48338b22a34519144008451af89f36889258d5723b70d0ea", _GAP, "Official Band 3 has no apparent logical organization and unhelpful paragraphing; v1's weak-organization wording understates the limitation."),
    _entry(_CC, 4, "ce426568e0a696e449fb7946711c17ffd3e997ad4812c342d396937b6909f80f", "writing-coherence-and-cohesion-band-4", "0127cfbacc05768e0fd355f56ca02902d068325a42ea9928cae6b204495be2cb", _GAP, "Official Band 4 has no clear progression, unreliable basic links, and possibly no usable paragraph topics; v1 is less severe."),
    _entry(_CC, 5, "bec53e05c0cb8fa77bd9b01d768d38448adc5cdc7968884aa6006602fc55aa5d", "writing-coherence-and-cohesion-band-5", "d2734de121a382bcae99cab067ecdb0033e68b34415036ba88312bb9a4c92fee", _GAP, "Official Band 5 may lack overall progression and paragraphing may be missing; v1's recognizable-progression wording is stronger."),
    _entry(_CC, 6, "0ed8019bb0c1ddc80fb868b52b818392d95e046c08f484595da1994f9b7cfa7a", "writing-coherence-and-cohesion-band-6", "32443bcea8e369af298a989308019fef31b0281301d9dd1cbecace29eb15a319", _GAP, "Official Band 6 allows mechanical or faulty cohesion and illogical paragraphing; v1 explicitly describes paragraphing as logical."),
    _entry(_CC, 7, "9aa68bc035690ce70c0eb3892d057d27ffbaa53228923d85c56024310c6a8a1a", "writing-coherence-and-cohesion-band-7", "f45849fe60131c77ea693edd86af34ae90d13b83500f748ea0e3d5c8177dd434", _GAP, "Official Band 7 permits cohesive-device inaccuracies and over- or under-use; v1's controlled-cohesion wording is stronger."),
    _entry(_CC, 8, "81871dcbdd30c860ff07a7e291400b484388011c87cfe948e6243ac05f221c6d", "writing-coherence-and-cohesion-band-8", "04f8f2350ad44d823e6bec95895572eb8330712b2d4108154868246e31b9b4b9", _GAP, "Official Band 8 requires sufficient appropriate paragraphing with occasional lapses; v1's skillful-paragraphing wording is stronger."),
    _entry(_CC, 9, "2354d9bc0be33e1797fe4c309f64afbfb093d79e5e2450d6957ffff79d555e7d", "writing-coherence-and-cohesion-band-9", "09fc274127c10266f34a118919bace5cbbf63d552c2203b8bdba878d1ce484ca", _MISSING, "Both describe effortless progression, unobtrusive cohesion, and highly controlled paragraphing; v1 lacks claim provenance."),
    _entry(_LR, 0, "407b681a3ee2bc8ea7d632f46222102078900c2add1c1a332b7bd76b9913b551", "writing-lexical-resource-band-0", "c968cdd7f600a485599bb1f71a4e945976ea210d3e15b55435095b10fd0dc09d", _MISSING, "Both leave no genuine response from which vocabulary can be assessed; v1 lacks the official Band 0 conditions and claim provenance."),
    _entry(_LR, 1, "8b569396c09a42a904f1d23a5aefc66d63cd156bf090f147c760ecf51d0fac85", "writing-lexical-resource-band-1", "3014787e37c639e596492c7b150edd61f39e6b113752652e60f367153aa08264", _MISSING, "Both describe no resource beyond isolated words; v1 lacks the official word-count condition and claim provenance."),
    _entry(_LR, 2, "4ed46629eda281d18993329892e06341a6819318019aca329ca4f6bddac8a9fc", "writing-lexical-resource-band-2", "16ab4422a9e64c930696fd4ac43968a439600a354284d3658d2d8d931e50c7a4", _MISSING, "Both describe an extremely limited resource without word-formation or spelling control; v1 lacks claim provenance."),
    _entry(_LR, 3, "10f4ce131dfc14910105082c5a9988e91672d7a5dbfe425b93d8c1b7f6e767f6", "writing-lexical-resource-band-3", "3a1e9795877da958090584b30385061596f3f6df6842a7a6773d8398fb057709", _MISSING, "Both describe inadequate or memorised vocabulary whose errors frequently impede meaning; v1 lacks claim provenance."),
    _entry(_LR, 4, "943c90b45ac49eee7e45d46685bd127dbeff1502c1acc118de79bb99dc5f5f6e", "writing-lexical-resource-band-4", "935e49525e6a49aea6407de93d9f46d1c7f99b8df85958873726ed67dba31c37", _GAP, "Official Band 4 vocabulary is limited and inadequate or unrelated, with errors that may impede meaning; v1 says basic vocabulary conveys meaning."),
    _entry(_LR, 5, "3b6cebc4d99018fd97954251895b23e2a13aa672edcdfcf619ae0c31264d3275", "writing-lexical-resource-band-5", "05c64e3228d06956a8c6b6db6961fc41b7c4e70bfb6bec5b1f4cdc334abd467c", _GAP, "Official Band 5 is limited and only minimally adequate, with little variation and frequent appropriacy lapses; v1 calls the range adequate."),
    _entry(_LR, 6, "ff3c9dff291f7fa16a221c70f7c4fda422208c58551ad5b406c4be2035fd3af5", "writing-lexical-resource-band-6", "6389be164b92d63b408788fceb7e35d8d6bd3481bc9b0c358e88028de304b7ae", _GAP, "Official Band 6 can be restricted or imprecise despite being generally adequate; v1's sufficiently-varied wording is stronger."),
    _entry(_LR, 7, "3cefbbd63b4d9a1288ac7f8d3f7a2d8f6f1487bf77c304dbbdc0bde1a2cd51ac", "writing-lexical-resource-band-7", "6739533bd8eef04374d39cceee2d7041680c502060c8436f3cd5918167aaf253", _GAP, "Official Band 7 shows some flexibility and less-common usage but still allows style and collocation lapses; v1 implies stronger control."),
    _entry(_LR, 8, "85d9216e9b54dfee7623e51c91d03e5d32bd61ac76ea5c6d770649716ef071cf", "writing-lexical-resource-band-8", "c5af16f04a8e233492e35896ba4eabe81e638dd298df83770f98ab320175f728", _MISSING, "Both describe wide, fluent, precise vocabulary with skilful uncommon usage and only occasional low-impact errors; v1 lacks claim provenance."),
    _entry(_LR, 9, "0d7033fc82c0c9700ab5639fb886b39e20cd29795eaca398ed42891903d8a891", "writing-lexical-resource-band-9", "65d3e53fcde94a7bc5e0d9f4705011ebe2f8a96112d1e7ef8d1f3faeee6205a1", _MISSING, "Both describe wide, natural, sophisticated, precise vocabulary with extremely rare errors; v1 lacks claim provenance."),
    _entry(_GRA, 0, "4c4f5cdc3d783a6539e6d54aa1fa7abf83aedf2724e464a7a51ccbb18e5e091f", "writing-grammatical-range-and-accuracy-band-0", "42ba9cc54246aa8245f3bb047b06d1199ee1f407c3362320f265ece97905604c", _MISSING, "Both leave no genuine response from which sentence control can be assessed; v1 lacks the official Band 0 conditions and claim provenance."),
    _entry(_GRA, 1, "953551b41cfd0888136b5212881298fd8354571bee672b9d7fce79904bc86aff", "writing-grammatical-range-and-accuracy-band-1", "2ff26e0372916e7dfb66ff326fa95d1133a4779eb48c4cff2e944d94029d5771", _MISSING, "Both describe no rateable grammar beyond fragments or isolated language; v1 lacks the official word-count condition and claim provenance."),
    _entry(_GRA, 2, "8c8a8541b827342cec360d086afe487f2e6ec58d42ea557d8dae255cc438117f", "writing-grammatical-range-and-accuracy-band-2", "b828c8b5e441be18896057bb6d3fe3c794c2c03c5f69a4e9135db6c282fa89ff", _MISSING, "Both describe almost no sentence forms and no sustained communication; v1 lacks claim provenance."),
    _entry(_GRA, 3, "61d9a218755bacd1e117ab674a1ae7179dee32aab17d7109ff2605b1fc8d7cf9", "writing-grammatical-range-and-accuracy-band-3", "f11f6b6f727a68ac38ae4ca43e161feee3d2a95b96a59d7144387b0d76345476", _MISSING, "Both describe grammar and punctuation errors dominating and preventing most meaning; v1 lacks claim provenance."),
    _entry(_GRA, 4, "a4d2735d7fdd29fa7614af3b8aa073dbe5815eb6aaf9dab696c3245f383daec3", "writing-grammatical-range-and-accuracy-band-4", "f86fa3f02dd35d97bdacd9761a8e8171775a30402735a92c14ec7a2524b4e842", _GAP, "Official Band 4 uses a very limited, mainly simple range with errors that may impede meaning; v1's limited-range/basic-meaning anchor is milder."),
    _entry(_GRA, 5, "797251a5d3ef91bf3b0ada363b4534bb20b8b62251c23b40c547ac5f7003b9c9", "writing-grammatical-range-and-accuracy-band-5", "1f2af20ed713ef1dddd8cdc46a02d6de16ce15a08496be90b3a3e9a02fa65b49", _MISSING, "Both describe limited repetitive forms, faulty complex attempts, frequent errors, and retained but difficult meaning; v1 lacks claim provenance."),
    _entry(_GRA, 6, "6b29cae4f4c012f85f481f2f6e3d36a00048422f78b86524b8763bd99a4df750", "writing-grammatical-range-and-accuracy-band-6", "944e61f1eb3acdc6cf03b720014197ee6b3518308a21dd212e1ddd89918c52d7", _MISSING, "Both describe simple and complex forms with limited complex accuracy and errors that rarely impede meaning; v1 lacks claim provenance."),
    _entry(_GRA, 7, "fc5601425c42d65e7269117850aa680c082e8182241126fe15873d11e52169df", "writing-grammatical-range-and-accuracy-band-7", "85f48e9437ed9179e7c55c6c666f6beb1020f143662e0faf8a53715492fa9e95", _MISSING, "Both describe varied complex forms, generally good grammar and punctuation control, and a few non-impeding errors; v1 lacks claim provenance."),
    _entry(_GRA, 8, "0dd75b69f53fc51d9281747367b9de9c074faf2b7028bd7c1998ee3662908fa1", "writing-grammatical-range-and-accuracy-band-8", "b6323afe9022e0abd06b79f27faad5d328cd9acecceea6583881ff2ee9dd4073", _MISSING, "Both describe a wide flexible range, mostly accurate sentences, and occasional low-impact lapses; v1 lacks claim provenance."),
    _entry(_GRA, 9, "5bd7dd3b685489b55c21bcba738a84d40f9b13711c57df93124102d0cb9e3c83", "writing-grammatical-range-and-accuracy-band-9", "84f3ad3c7230770e05520239833893a182c3ae36714351aeb9171a386ea68c8d", _MISSING, "Both describe a wide fully controlled range with extremely rare grammar or punctuation errors; v1 lacks claim provenance."),
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
