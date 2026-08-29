# Phase 11 Existing Knowledge & Product Surface Audit

## Audit status

```text
P11-01 = COMPLETE
P11-01 External Audit Review = PENDING
P11-02 = BLOCKED_BY_EXTERNAL_AUDIT_REVIEW
```

This is a documentation-only audit of the implementation that exists before
the Phase 11 Wiki contract is frozen. It does not authorize P11-02 or any Wiki
runtime implementation.

Audited repository state:

```text
repository = bluesblue320-hue/ielts-learning-agent
branch = phase/11-writing-wiki-knowledge-v1
Phase 10 merge baseline = c7a5f991df9c556408295d01194f1f17c13653b5
Phase 11 Graph Review = APPROVED
```

## 1. Audit method and scope

The audit inspected the actual Phase 9/10 schemas, static registries,
retrieval code, rubric compatibility ledger, learner guidance service,
practice-generation boundary, FastAPI router registration, typed Web client,
dashboard rendering, Knowledge grounding evaluator, and their focused tests.

The authoritative implementation files inspected were:

```text
app/schemas/knowledge.py
app/knowledge/__init__.py
app/knowledge/sources.py
app/knowledge/writing_task2_v1.py
app/knowledge/retriever.py
app/knowledge/rubric_compatibility.py
app/services/writing_guidance.py
app/services/practice_generation.py
app/llm/practice_generator.py
app/api/routes/practice.py
app/main.py
app/eval/knowledge.py
web/src/lib/api/client.ts
web/src/app/dashboard/page.tsx
```

Relevant Knowledge, guidance, generation, API, Web, and Eval tests were also
inspected. No intended Wiki schema or future route was treated as implemented.

## 2. Frozen Phase 9 contracts

The implementation exposes and validates these frozen identifiers:

| Contract | Identifier | Current owner |
| --- | --- | --- |
| Knowledge snapshot | `ielts-writing-knowledge-v1` | Phase 9 static `KnowledgeUnit` corpus |
| structured retrieval | `writing-knowledge-structured-v1` | provider-free deterministic retriever |
| grounded guidance | `writing-grounded-guidance-v1` | application-assembled learner guidance response |

The current schema boundary contains `KnowledgeUnit`, `KnowledgeSource`,
`KnowledgeSourceRef`, `KnowledgeCategory`, `KnowledgeRetrievalQuery`, and
`KnowledgeRetrievalResult`.

All Phase 9 Knowledge Pydantic models inherit a boundary configured with
`extra="forbid"` and `frozen=True`. Stable IDs are stripped, bounded, and
restricted to lowercase letters, digits, and hyphens. `KnowledgeUnit` fixes the
task to `writing_task2`, fixes the Knowledge version, requires one to four
source references, and restricts descriptor bands to integers from 0 through
9. Category-specific validation requires criteria for assessment/band units
and a task type for task-understanding units.

`KnowledgeSource` records closed authority/source-type enums, publisher, title,
URL, a verification string matching `YYYY-MM-DD`, Writing Task 2 scope, and an
optional source revision. `KnowledgeSourceRef` requires a stable source ID and
a non-blank locator, with optional page and section metadata.

`KnowledgeRetrievalQuery` owns the closed purpose enum. It requires a criterion
for every current purpose, current band for rubric compatibility, target band
for practice generation, and both current and target band for learner guidance.
It has no raw-text, learner-ID, semantic-search, or provider-controlled query
field.

## 3. Canonical Knowledge corpus

Executable inspection of `WRITING_TASK2_KNOWLEDGE_UNITS` and
`validate_snapshot_integrity()` verified this exact inventory:

| Category | Count | Canonical meaning |
| --- | ---: | --- |
| `assessment` | 4 | one unit for each Writing Task 2 assessment criterion |
| `band_guidance` | 40 | four criteria × integer bands 0–9 |
| `task_rule` | 3 | minimum 250 words, connected text, answer the prompt directly |
| `task_understanding` | 7 | canonical Task 2 task types |
| **Total** | **54** | unique source-backed `KnowledgeUnit` objects |

The seven task types are:

```text
opinion
discussion
multi_part
multi_part_opinion
advantage_disadvantage
positive_negative
cause_solution
```

Official descriptor Knowledge is integer-band based. There are no half-band
KnowledgeUnits or IDs such as `band-6-5`. Product half-bands are mapped to
integer descriptor units by retrieval; they are not persisted as new factual
Knowledge.

Snapshot initialization fails closed when Knowledge IDs are duplicated, a
unit's version differs from `ielts-writing-knowledge-v1`, or a referenced
source ID is absent from the canonical registry. Non-blank locators are already
enforced by `KnowledgeSourceRef` validation.

## 4. Source and provenance baseline

`KNOWLEDGE_SOURCES` is an immutable `MappingProxyType` registry containing
exactly four sources. Every current source has authority `official_ielts`,
publisher `IELTS`, source type `official_web_or_pdf`, and Writing Task 2 scope.

| Source ID | Title | Verified | Source revision |
| --- | --- | --- | --- |
| `ielts-writing-band-descriptors-2023` | IELTS Writing Band Descriptors | `2026-08-21` | `2023-05` |
| `ielts-writing-key-assessment-criteria` | IELTS Writing Key Assessment Criteria | `2026-08-21` | not recorded |
| `ielts-writing-task2-question-prompts-2023` | IELTS Writing Task 2: How to understand IELTS question prompts | `2026-08-21` | `2023-02-01` |
| `ielts-academic-writing-format` | IELTS Academic: Writing test format | `2026-08-21` | not recorded |

The registered `https://ielts.org/...` URLs are provenance metadata. Runtime
Knowledge assembly is checked into Git, provider-free, and network-independent;
the retriever does not fetch or crawl those URLs. Every canonical KnowledgeUnit
has at least one resolving `KnowledgeSourceRef` with a claim locator.

## 5. Deterministic retrieval baseline

`retrieve_knowledge()` validates the complete snapshot on every call, selects
units through a closed structured query, preserves corpus declaration order,
deduplicates by `knowledge_id`, applies a purpose-specific limit, and returns an
immutable versioned result.

Current limits are:

| Purpose | Maximum results |
| --- | ---: |
| `practice_generation` | 7 |
| `learner_guidance` | 8 |
| `rubric_compatibility` | 2 |

Purpose behavior is:

- rubric compatibility returns descriptor units only, using `current_band`;
- practice generation uses the target-band descriptor units, then the criterion
  unit, an exact matching task-type unit only when `query.task_type` is present,
  and the three task-rule units;
- learner guidance combines current- and target-band descriptor units, then
  the criterion unit, an optional exact task-type unit, and the three rules;
- the final ID deduplication protects overlapping current/target descriptor
  selections, although filtering the unique corpus already avoids duplicates.

Half-band mapping is exact and bounded:

| Product band | Descriptor bands |
| ---: | --- |
| `6.0` | `(6,)` |
| `6.5` | `(6, 7)` |
| `7.0` | `(7,)` |
| `7.5` | `(7, 8)` |
| `9.0` | `(9,)` |

`9.0` does not overflow to Band 10. Integer inputs map to one descriptor; a
validated half-band maps to its lower and upper adjacent integer descriptors.

### Task-type retrieval finding

All seven task-type units exist and the generic retriever can return an exact
task-type match. However, both actual adaptive callers construct
`KnowledgeRetrievalQuery` without `task_type`:

```text
WritingGuidanceService
PracticeGenerationService._knowledge_context
```

Therefore task-type Knowledge is currently absent from learner guidance and
practice-generation Knowledge context. For example, Task Response guidance for
current `6.5` and target `7.0` returns descriptor Bands 6 and 7, the criterion
unit, and the three task rules; it returns no task-type unit. Practice generation
for target `7.0` returns Band 7, the criterion unit, and the same rules.

This is an audit input, not a P11-01 defect repair:

```text
Wiki browseability of task-type Knowledge
!=
authorization to modify Phase 9 adaptive retrieval
```

## 6. Rubric compatibility baseline

`RUBRIC_COMPATIBILITY_LEDGER` contains exactly 40 explicit reviewed entries:
four Writing criteria × integer bands 0–9. Each frozen dataclass entry records
criterion, band, rubric text SHA-256, one or more aligned Knowledge IDs,
Knowledge statement SHA-256, a closed compatibility status, and a non-blank
rationale.

The validator requires exact 40-key coverage, rejects duplicates/unexpected
keys, resolves and dimension-checks every Knowledge reference, and fails when
either the frozen rubric wording or Knowledge statement wording no longer
matches the reviewed hashes.

Verified current status distribution:

| Status | Count |
| --- | ---: |
| `compatible_with_missing_provenance` | 23 |
| `gap_requires_documentation` | 17 |
| `compatible` | 0 |
| `material_conflict` | 0 |

The ledger is reviewed compatibility evidence for two existing frozen inputs.
It does not authorize Wiki topology:

```text
Rubric compatibility metadata
!=
automatic Wiki semantic relation authority
```

P11-01 does not convert ledger entries into Wiki edges.

## 7. Grounded guidance baseline

The implemented authority chain is:

```text
latest accepted LearningUpdate ordered by id DESC
    ↓
PracticeRecommendation owned by that learner and update
    ↓
reconstructed persisted planning snapshot
    ↓
KnowledgeRetrievalQuery(learner_guidance)
    ↓
canonical KnowledgeUnits
    ↓
application-owned GroundedCitation objects
    ↓
WritingGroundedGuidanceResponse
```

The service does not reconstruct learner truth from browser state. It uses the
persisted recommendation snapshot, target skill, current estimate rounded
half-up to the nearest half band, and learner target band. A no-practice
decision does not invent a training target or guidance item.

Learner-facing explanation text is the deterministic Chinese-semicolon join of
the retrieved `KnowledgeUnit.statement` values. Citation identity and public
metadata come from the application registry, not the provider. Citations are
deduplicated by:

```text
(source_id, locator)
```

`GroundedGuidanceItem` exposes both `knowledge_ids` and item citations, while
the response also exposes the deduplicated top-level `source_citations`. This
is the existing Phase 11 integration seam:

```text
GroundedGuidanceItem.knowledge_ids
        ↓
canonical KnowledgeUnit
        ↓
future canonical WikiPage
```

No bridge is implemented by P11-01.

## 8. Practice-generation grounding baseline

The active Phase 9 generation contract uses:

```text
generator policy = writing-practice-generation-v2
prompt version = practice-generation-v2
Knowledge context = writing-practice-knowledge-context-v1
Knowledge version = ielts-writing-knowledge-v1
retrieval version = writing-knowledge-structured-v1
```

`PracticeKnowledgeContext` contains one to seven immutable
`PracticeKnowledgeItem` objects. Each item carries:

```text
knowledge_id
statement
source_ids
```

The service builds these fields from deterministic canonical retrieval; the
provider does not create Knowledge or source identity. Historical generation
v1 is explicitly prevented from carrying Phase 9 Knowledge context, while v2
requires the v2 prompt and a non-empty context.

The authority boundary remains:

```text
Persisted PracticeRecommendation controls WHAT is trained.
Generator / provider controls HOW the exercise is phrased.
```

The recommendation owns target skill, decision type, planner version, target
band, and reason codes. Generated output must mirror the target skill; mismatch
raises `GeneratedPracticeAuthorityError` and creates no practice row. Phase 11
Wiki cannot become Planner or practice-target authority.

## 9. Current public API surface

Actual `create_app()` registration includes health, Writing evaluation,
learner/state, granular practice, Memory, and Agent routers. There is no current
generic public Knowledge or Wiki browsing route equivalent to:

```text
GET /knowledge
GET /wiki
GET /knowledge/search
```

The existing learner-facing Knowledge-bearing read endpoint is:

```text
GET /learners/{learner_id}/writing/guidance
```

It is a provider-free learner guidance projection, not a generic Wiki API.
Therefore P11-08 would add a genuinely new read-only product surface rather
than replace an existing Wiki endpoint.

## 10. Current Web product surface

The typed client currently models:

- `GroundedCitation`: `source_id`, publisher, title, URL, locator, optional page
  and section;
- `GroundedGuidanceItem`: criterion, title, explanation, `knowledge_ids`, and
  citations;
- `WritingGroundedGuidanceResponse`: guidance items, top-level citations, and
  the three frozen version identifiers.

The dashboard renders the grounded explanation plus citation publisher, source
title, external URL, and locator. It does not render raw Knowledge IDs or source
IDs to the learner; the Phase 9 browser regression explicitly checks their
absence.

The future integration seam is internal and stable:

```text
internal stable knowledge_id
        ↓
future canonical WikiPage lookup
        ↓
learner-facing internal Wiki navigation
```

P11-01 does not implement this navigation.

## 11. Existing Phase 10 Knowledge Eval seam

`app/eval/knowledge.py` already provides the deterministic
`KNOWLEDGE_GROUNDING` evaluator and application-shaped `GroundingEvidence`.
It validates the snapshot before evaluation and currently fails closed for:

| Failure family | Existing failure code / behavior |
| --- | --- |
| invalid snapshot | `knowledge_snapshot_integrity` |
| unknown Knowledge ID | `knowledge_unknown_id` |
| unknown unit provenance | `knowledge_unknown_provenance` |
| evidence/ID mismatch | `knowledge_evidence_identity_mismatch` |
| provider-owned or altered citation identity | `knowledge_provider_invented_citation` |
| unknown citation source/locator | `knowledge_unknown_citation` |
| incomplete citation coverage | `knowledge_citation_coverage_mismatch` |
| learner/update/recommendation/query mismatch | `knowledge_recommendation_context_mismatch` |
| generation carrying guidance-shaped citations | `knowledge_generation_citations_not_application_shaped` |
| practice source map mismatch | `knowledge_generation_source_mismatch` |
| retrieval nondeterminism | `knowledge_retrieval_not_deterministic` |
| practice Knowledge outside deterministic retrieval | `knowledge_practice_scope_mismatch` |

The recommendation/query check covers learner and update ownership, practice
decision validity, target skill, target band, normalized current band, and
allowed guidance/generation purpose. Citation expectations are reconstructed
from canonical units and the source registry. Practice generation must match
the exact deterministic ordered Knowledge IDs and per-unit source IDs.

Phase 11 must extend this Phase 10 Eval architecture for Wiki-specific
resolution, topology, provenance, and authority cases. P11-01 does not create a
separate Wiki Eval framework.

## 12. Decisions P11-02 must freeze

P11-02 remains blocked pending external review of this audit. It must freeze:

1. exact Wiki and navigation versions;
2. exact page types, stable page IDs, canonical topology, titles, aliases,
   breadcrumbs, grouping labels, and navigation-label semantics;
3. exactly one primary WikiPage owner for every canonical KnowledgeUnit;
4. whether secondary references are allowed and, if allowed, their
   deduplication, ordering, and presentation semantics;
5. deterministic Knowledge ID → canonical WikiPage reverse lookup and
   ambiguity failure behavior;
6. root policy, parent multiplicity, full 54-unit reachability, and cycle policy;
7. the closed structural relation taxonomy, directionality, symmetry, inverse
   behavior, ordering, rationale, and validation rules;
8. semantic-relation evidence/authority rules and whether semantic relations
   are included at all in Wiki v1;
9. deterministic ID/title/alias/token/prefix lookup semantics, if text lookup
   is included;
10. exact read-only API routes, public response schemas, provenance fields,
    not-found/invalid-query error semantics, and safe bounds;
11. the frontend route, breadcrumbs, accessibility behavior, and citation →
    Wiki navigation contract;
12. whether the seven task-type pages are browse-only in Wiki v1, preserving
    current adaptive retrieval unless separately authorized;
13. Phase 10 Eval extension cases and veto/major failure expectations;
14. Wiki compatibility and version-change policy.

These are design inputs, not decisions made by this audit except where the
approved Graph already freezes an authority invariant.

## 13. Explicit non-goals and non-authorization

P11-01 authorizes none of the following:

```text
new IELTS factual claims
changes to ielts-writing-knowledge-v1
changes to writing-knowledge-structured-v1
changes to writing-grounded-guidance-v1
changes to writing-task2-v1
scoring changes
learner-state changes
Planner changes
Memory changes
Agent authority changes
Vector DB
embeddings
semantic search
RAG
GraphRAG
LangChain
LangGraph
Neo4j
runtime web search
runtime crawling
LLM-generated Wiki pages
LLM-generated Wiki relations
new PostgreSQL tables
migrations
new dependencies
Speaking
Reading
Listening
authentication
payments
```

No application, test, Web runtime, migration, or dependency file is changed by
this audit.

## 14. Validation evidence

Read-only executable inspection verified:

```text
KnowledgeUnits = 54
categories = assessment 4, band_guidance 40, task_rule 3, task_understanding 7
registered sources = 4
rubric compatibility entries = 40
compatibility statuses = 23 missing-provenance, 17 documented-gap, 0 conflict
retrieval limits = practice 7, guidance 8, rubric compatibility 2
descriptor mappings = 6.0→6, 6.5→6/7, 7.0→7, 7.5→7/8, 9.0→9
```

The focused provider-free validation command was:

```text
.venv/Scripts/python.exe -m pytest -q
  tests/test_knowledge_schemas.py
  tests/test_knowledge_snapshot.py
  tests/test_knowledge_retriever.py
  tests/test_rubric_knowledge_compatibility.py
  tests/test_writing_guidance.py
  tests/test_guidance_api.py
  tests/test_phase9_practice_grounding.py
  tests/test_phase9_grounding_hardening.py
  tests/test_eval_knowledge.py
```

Result:

```text
48 passed in 0.65s
1 existing Starlette/httpx deprecation warning
```

No full backend/frontend suite was required for this documentation-only audit.

## 15. Stop state

```text
P11-00 = COMPLETE
Phase 11 Graph Review = APPROVED
P11-01 = COMPLETE
P11-01 External Audit Review = PENDING
P11-02 = BLOCKED_BY_EXTERNAL_AUDIT_REVIEW
P11-03 onward = BLOCKED
```

STOP. Do not begin P11-02 until the external audit review is explicitly
APPROVED.
