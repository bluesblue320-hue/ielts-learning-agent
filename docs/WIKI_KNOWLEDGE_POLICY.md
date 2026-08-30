# Phase 11 Wiki Knowledge Policy

## Status and scope

This document is the normative P11-02 contract for the static, read-only IELTS
Writing Task 2 Wiki. Later Phase 11 nodes must implement this contract without
changing its authority boundaries or silently widening its scope.

Implementation note: P11-03 through P11-13 now implement the frozen schemas,
58-page registry, relation ledger, validation, deterministic service, read-only
API, Web experience, citation bridge, and Eval/browser coverage. This note does
not alter the normative P11-02 contract.

```text
Wiki version = ielts-writing-wiki-v1
Navigation version = writing-wiki-navigation-v1
Knowledge version = ielts-writing-knowledge-v1
Canonical pages = 58
Canonical KnowledgeUnits = 54
Canonical relations = 93
Secondary Knowledge references = NOT SUPPORTED
Semantic relations = OUT OF SCOPE FOR WIKI V1
Relation authority = application_structural
```

P11-02 freezes documentation only. It does not implement schemas, registries,
relations, validators, services, API routes, Web pages, Eval cases, database
objects, or tests.

## 1. Normative language

`MUST`, `MUST NOT`, `SHALL`, and `SHALL NOT` are contract requirements.
`MAY` identifies an implementation choice that does not change the frozen
semantics. A later implementation must fail closed when it cannot satisfy a
requirement.

## 2. Version identifiers and compatibility

The exact identifiers are:

```text
ielts-writing-wiki-v1
writing-wiki-navigation-v1
```

Every public Wiki response MUST carry both identifiers. Every Wiki registry
object MUST be validated against `ielts-writing-wiki-v1`; every navigation
projection MUST be validated against `writing-wiki-navigation-v1`.

A new Wiki version or an explicit compatibility review is required for any
change to:

- the canonical page set or a canonical page ID;
- `WikiPageType` membership or meaning;
- primary Knowledge ownership or projection semantics;
- relation membership, canonical identity, authority, authority basis,
  rationale policy, or meaning;
- the authority boundary between Knowledge and Wiki;
- public Wiki response semantic meaning;
- removal of a canonical page.

A new navigation version or an explicit compatibility review is required for
any change to:

- a canonical parent, child, root, or breadcrumb path;
- sibling or full-index ordering;
- a canonical title or alias;
- identity normalization or lookup resolution;
- adjacent-band navigation behavior;
- the meaning of navigation labels.

A change that affects both groups requires review of both versions. Pure UI
wording outside canonical page titles, aliases, breadcrumbs, relation labels,
and response semantics MAY remain compatible. Presentation wording is not
compatible merely because it is described as cosmetic when it changes page
identity, ownership, topology, relation semantics, lookup semantics, or API
meaning.

Source-backed Knowledge statement changes remain governed by the Knowledge
versioning process. The Wiki MUST pin `ielts-writing-knowledge-v1`, fail closed
on a different Knowledge version, and undergo compatibility review before it
adopts a new Knowledge snapshot. It MUST NOT silently absorb Knowledge semantic
changes.

## 3. Authority model

The frozen authority chain is:

```text
Official IELTS Source
        ↓
KnowledgeSourceRef
        ↓
KnowledgeUnit
        ↓
WikiPage / WikiRelation
        ↓
Navigation / Presentation
```

`KnowledgeUnit` remains the factual authority. A Wiki page may contain only:

1. a deterministic projection or composition of the KnowledgeUnits it owns;
2. application-owned organization and presentation metadata that introduces
   no new normative IELTS factual meaning.

The Wiki MUST NOT create, paraphrase into a new claim, infer, or become the
source of normative IELTS facts. A new IELTS factual meaning must first become
a reviewed, source-backed KnowledgeUnit under the existing Knowledge authority.

Page IDs, page types, titles, aliases, breadcrumbs, grouping labels, ordering,
and navigation labels are application-owned metadata. They MUST NOT be
presented as official IELTS provenance.

## 4. Closed page-type contract

`WikiPageType` is the following closed enum and no other value is valid:

```text
root
section
criterion
band_descriptor
task_rule
task_type
```

| Page type | Cardinality | Knowledge ownership |
| --- | ---: | --- |
| `root` | 1 | exactly zero |
| `section` | 3 | exactly zero |
| `criterion` | 4 | exactly one assessment KnowledgeUnit |
| `band_descriptor` | 40 | exactly one band-guidance KnowledgeUnit |
| `task_rule` | 3 | exactly one task-rule KnowledgeUnit |
| `task_type` | 7 | exactly one task-understanding KnowledgeUnit |
| **Total** | **58** | **54 owned KnowledgeUnits** |

Generic article, topic, tag, collection, search-result, and generated page
types are not part of Wiki v1.

## 5. Canonical page registry and IDs

Canonical page IDs are stable, unique, lowercase ASCII identifiers containing
only letters, digits, and single hyphens between segments. They do not expose
filesystem paths, do not depend on array positions, and are not derived at
runtime from display text.

### 5.1 Root and sections

| Order | Page ID | Type | Exact title | Parent |
| ---: | --- | --- | --- | --- |
| 1 | `writing-task2` | `root` | Writing Task 2 | none |
| 1 | `writing-task2-assessment` | `section` | Assessment Criteria | `writing-task2` |
| 2 | `writing-task2-task-rules` | `section` | Task Rules | `writing-task2` |
| 3 | `writing-task2-task-types` | `section` | Task Types | `writing-task2` |

The root and the three sections are organization-only pages. They own no
KnowledgeUnit and MUST NOT copy Knowledge statements into independent content.

### 5.2 Criteria and band descriptors

The criterion groups are frozen in this order:

| Order | Criterion key | Criterion page ID | Exact title | Owned criterion Knowledge ID |
| ---: | --- | --- | --- | --- |
| 1 | `task_response` | `writing-task2-task-response` | Task Response | `writing-task-response-criterion` |
| 2 | `coherence_and_cohesion` | `writing-task2-coherence-and-cohesion` | Coherence and Cohesion | `writing-coherence-and-cohesion-criterion` |
| 3 | `lexical_resource` | `writing-task2-lexical-resource` | Lexical Resource | `writing-lexical-resource-criterion` |
| 4 | `grammatical_range_and_accuracy` | `writing-task2-grammatical-range-and-accuracy` | Grammatical Range and Accuracy | `writing-grammatical-range-and-accuracy-criterion` |

Each criterion page is a direct child of `writing-task2-assessment`. Each owns
the one assessment KnowledgeUnit shown above.

For each criterion row and each integer `band` from 0 through 9 inclusive,
there is exactly one direct child band page:

```text
page_id = writing-task2-{criterion-slug}-band-{band}
title = {Criterion Title} Band {band}
owned Knowledge ID = writing-{criterion-slug}-band-{band}
```

The exact criterion slugs are:

```text
task-response
coherence-and-cohesion
lexical-resource
grammatical-range-and-accuracy
```

Band pages are ordered numerically from 0 through 9. This rule freezes all 40
page IDs, unique titles, parent assignments, and Knowledge mappings. There are
no half-band Wiki pages because the frozen Knowledge snapshot has no half-band
descriptor KnowledgeUnits.

### 5.3 Task rules

These pages are direct children of `writing-task2-task-rules` in the frozen
Phase 9 declaration order:

| Order | Page ID | Exact title | Owned Knowledge ID |
| ---: | --- | --- | --- |
| 1 | `writing-task2-rule-minimum-250-words` | Minimum 250 Words | `writing-task2-minimum-250-words` |
| 2 | `writing-task2-rule-connected-text` | Connected Text | `writing-task2-connected-text` |
| 3 | `writing-task2-rule-answer-prompt-directly` | Answer the Prompt Directly | `writing-task2-answer-prompt-directly` |

### 5.4 Task types

These pages are direct children of `writing-task2-task-types` in the frozen
Phase 9 declaration order:

| Order | Page ID | Exact title | Owned Knowledge ID |
| ---: | --- | --- | --- |
| 1 | `writing-task2-type-opinion` | Opinion | `writing-task2-type-opinion` |
| 2 | `writing-task2-type-discussion` | Discussion | `writing-task2-type-discussion` |
| 3 | `writing-task2-type-multi-part` | Multi-part | `writing-task2-type-multi-part` |
| 4 | `writing-task2-type-multi-part-opinion` | Multi-part Opinion | `writing-task2-type-multi-part-opinion` |
| 5 | `writing-task2-type-advantage-disadvantage` | Advantage / Disadvantage | `writing-task2-type-advantage-disadvantage` |
| 6 | `writing-task2-type-positive-negative` | Positive / Negative | `writing-task2-type-positive-negative` |
| 7 | `writing-task2-type-cause-solution` | Cause / Solution | `writing-task2-type-cause-solution` |

### 5.5 Page-count proof

```text
1 root
+ 3 sections
+ 4 criterion pages
+ 40 band-descriptor pages
+ 3 task-rule pages
+ 7 task-type pages
= 58 canonical Wiki pages
```

The canonical registry MUST contain exactly these 58 pages. An extra, missing,
or duplicate page is an integrity failure.

## 6. Knowledge ownership and reverse lookup

Every canonical KnowledgeUnit in `ielts-writing-knowledge-v1` has exactly one
primary canonical WikiPage owner:

```text
assessment unit        → matching criterion page
band-guidance unit     → matching criterion-and-band page
task-rule unit         → matching task-rule page
task-understanding unit → matching task-type page
```

Root and section pages own no Knowledge. Every other page owns exactly one
KnowledgeUnit. Secondary Knowledge references are not supported in Wiki v1.
The same KnowledgeUnit MUST NOT appear as content on another page.

Canonical reverse lookup is total and single-valued over the 54-unit snapshot:

```text
knowledge_id → exactly one primary page_id
```

Unknown Knowledge IDs, missing ownership, duplicate ownership, category/page
type mismatch, criterion mismatch, band mismatch, and task-type mismatch all
fail closed. There is no fallback to a section, source, or approximate page.

## 7. Canonical topology and tree policy

The canonical `contains` hierarchy is one rooted tree:

```text
Writing Task 2
├── Assessment Criteria
│   ├── Task Response
│   │   └── Task Response Band 0 ... Band 9
│   ├── Coherence and Cohesion
│   │   └── Coherence and Cohesion Band 0 ... Band 9
│   ├── Lexical Resource
│   │   └── Lexical Resource Band 0 ... Band 9
│   └── Grammatical Range and Accuracy
│       └── Grammatical Range and Accuracy Band 0 ... Band 9
├── Task Rules
│   ├── Minimum 250 Words
│   ├── Connected Text
│   └── Answer the Prompt Directly
└── Task Types
    ├── Opinion
    ├── Discussion
    ├── Multi-part
    ├── Multi-part Opinion
    ├── Advantage / Disadvantage
    ├── Positive / Negative
    └── Cause / Solution
```

The following are mandatory:

- `writing-task2` is the single root and has no parent;
- every other canonical page has exactly one structural parent;
- all 58 pages are reachable from the root;
- the `contains` hierarchy is acyclic;
- there is no self-edge, duplicate edge, orphan, or second parent;
- a band page belongs only to its matching criterion;
- a rule page belongs only under Task Rules;
- a task-type page belongs only under Task Types;
- adjacent-band relations do not affect parenthood or root reachability.

The tree contains exactly 57 canonical `contains` relations.

## 8. Relation contract

`WikiRelationType` is the following closed enum:

```text
contains
adjacent_band
```

`WikiRelationAuthority` is the following closed enum and no other authority
value is valid in Wiki v1:

```text
application_structural
```

Every canonical Wiki v1 relation MUST declare:

```text
authority = application_structural
```

`application_structural` means an application-owned navigation/topology
relation derived deterministically from this frozen Wiki contract and existing
canonical metadata. It is not official IELTS provenance, `KnowledgeSource`
authority, a source-backed semantic IELTS claim, pedagogical evidence, or
Planner authority.

The conceptual canonical `WikiRelation` contract has exactly these semantic
fields:

```text
relation_type: WikiRelationType
authority: WikiRelationAuthority
source_page_id: string
target_page_id: string
```

Wiki v1 relations have no `source_id`, `knowledge_id`, `provider_id`, semantic
confidence, embedding score, generation timestamp, or LLM-authored rationale.
Application structural authority MUST NOT be exposed or interpreted as IELTS
source provenance.

Semantic relations are out of scope for Wiki v1. The following values and
equivalent inferred meanings are prohibited:

```text
related_to
applies_to
supports
improves
prerequisite_of
```

### 8.1 `contains`

`contains` is structural, directional, and not symmetric. Its canonical
orientation is parent `source_page_id` to direct child `target_page_id`. It
MUST match the frozen tree and MUST NOT skip hierarchy levels.

Its authority basis is the canonical parent/child assignment frozen in this
policy. That assignment is mechanically validated against the 58-page rooted
tree; it does not come from an IELTS source document.

### 8.2 `adjacent_band`

`adjacent_band` is structural and semantically undirected. It exists only
between descriptor pages for numerically adjacent integer bands within the
same criterion. It is stored once in normalized order:

```text
source_page_id = lower-band page
target_page_id = higher-band page
higher band = lower band + 1
```

The endpoint orientation is canonical storage order, not a directed learning
meaning. Presentation MAY derive `previous_band` and `next_band` navigation
from it. There are exactly 9 adjacent pairs per criterion and 36 canonical
`adjacent_band` relations in total.

It MUST NOT mean recommended progression, learning path, prerequisite, score
improvement, next lesson, or Planner instruction. Cross-criterion, equal-band,
nonconsecutive, self, reversed duplicate, and repeated adjacent-band relations
are invalid.

Its authority basis is the conjunction of:

```text
same criterion
+ descriptor bands differ by exactly 1
+ lower-band/higher-band canonical normalization
```

This basis is mechanically validated from page metadata. It does not come from
an IELTS source document and does not establish a pedagogical or factual IELTS
relation.

Relations have no separate public ID in v1. Their canonical identities are:

```text
contains: (contains, parent_page_id, child_page_id)
adjacent_band: (adjacent_band, lower_page_id, higher_page_id)
```

### 8.3 Rationale policy

Canonical relation ledger rationale is not stored and is not required for
either Wiki v1 relation type. The frozen parent assignment is the complete
`contains` rationale; same criterion plus consecutive integer bands and
canonical lower/higher normalization is the complete `adjacent_band`
rationale.

Developers MUST NOT author 93 repetitive free-text rationales. Arbitrary
free-text rationale MUST NOT become a second semantic authority and is not a
field of the Wiki v1 relation schema. Validator diagnostics MAY explain why a
relation is invalid, but such messages are transient diagnostics and are not
persisted relation rationale.

## 9. Deterministic ordering

All sibling order values are explicit, application-owned, one-based ordinals.
They MUST NOT depend on dict or set iteration.

Frozen orders are:

1. root children: Assessment Criteria, Task Rules, Task Types;
2. criteria: Task Response, Coherence and Cohesion, Lexical Resource,
   Grammatical Range and Accuracy;
3. bands: numeric Band 0 through Band 9;
4. task rules: the Phase 9 declaration order in section 5.3;
5. task types: the Phase 9 declaration order in section 5.4.

The full index order is deterministic depth-first preorder: emit a page, then
its children recursively in sibling order. The global canonical relation
ledger is ordered first by relation-type order `contains`, `adjacent_band`,
then by the canonical full-page order of source and target. A page-detail
relation list is produced only by filtering incident relations from this
already ordered global ledger; it MUST NOT be independently or unstably
re-sorted. Knowledge and source projections preserve their frozen upstream
declaration order except for the explicit deduplication rule in section 14.

## 10. Titles, aliases, and identity lookup

The exact canonical English titles are frozen by section 5. They are
application-owned labels, not IELTS-source quotations. Wiki v1 defines an
explicit empty alias tuple for every canonical page. No implicit acronym,
translation, filename, slug, Knowledge ID, or source title is an alias.

Later aliases may be added only through navigation compatibility review and a
checked-in registry change. Runtime-generated aliases are prohibited.

The deterministic identity normalizer is:

1. require a string of at most 120 Unicode code points;
2. apply Unicode NFKC normalization;
3. trim surrounding Unicode whitespace;
4. collapse each internal run of Unicode whitespace to one ASCII space;
5. apply Unicode `casefold`.

An empty normalized value is invalid. Normalization does not remove
punctuation, hyphens, or slashes.

Resolution order is:

1. exact canonical page ID match wins;
2. otherwise resolve an exact normalized canonical title;
3. otherwise resolve an exact normalized explicit alias;
4. no match fails closed;
5. more than one match at any non-ID step fails closed as ambiguous.

Registry validation MUST reject collisions among normalized titles, aliases,
and canonical IDs even though canonical ID has runtime precedence. Prefix,
substring, token, fuzzy, semantic, embedding, ML, and LLM-ranked lookup are not
supported. There is no bounded prefix lookup in Wiki v1.

## 11. Task-type browse-only policy

The seven task-type KnowledgeUnits and pages are browseable Wiki content. They
are browse-only with respect to existing adaptive retrieval.

Phase 11 MUST NOT change `WritingGuidanceService` or
`PracticeGenerationService` queries to inject `task_type` merely because these
pages exist. Wiki browseability changes discoverability only; it does not
authorize a change to `writing-knowledge-structured-v1`, guidance results,
practice-generation context, Planner behavior, or practice-target authority.

## 12. Read-only API contract

The canonical API routes are:

```text
GET /knowledge/writing/wiki
GET /knowledge/writing/wiki/{page_id}
```

The index route accepts one optional query parameter:

```text
q: string, maximum 120 Unicode code points
```

With no `q`, the index route returns `WikiIndexResponse`. With `q`, it applies
section 10 lookup and returns `WikiPageDetail` for the one resolved canonical
page. The detail route accepts canonical page IDs only and returns
`WikiPageDetail`.

No Wiki v1 route accepts `POST`, `PUT`, `PATCH`, or `DELETE`. There is no admin,
ingestion, mutation, refresh, or provider-backed endpoint.

### 12.1 Public response schemas

Later P11-03 schemas MUST expose these exact semantic fields. Names are frozen;
Python container choices may use immutable tuples internally while JSON uses
arrays.

`WikiPageSummary`:

```text
page_id: string
page_type: WikiPageType
title: string
aliases: array[string]
parent_page_id: string | null
order: integer >= 1
has_knowledge: boolean
```

For the root, `parent_page_id` is null and `order` is 1. `has_knowledge` is
false only for the root and section pages.

`WikiBreadcrumb`:

```text
page_id: string
title: string
```

Breadcrumbs are root-first and include the current page as their final item.

`WikiSourceProjection`:

```text
source_id: string
authority: string
publisher: string
title: string
url: string
source_type: string
verified_at: string
source_revision: string | null
locator: string
page: integer | null
section: string | null
```

`WikiKnowledgeProjection`:

```text
knowledge_id: string
knowledge_version: string
task: string
category: KnowledgeCategory
statement: string
criterion: string | null
descriptor_band: integer | null
task_type: string | null
sources: array[WikiSourceProjection]
```

`WikiRelationView`:

```text
relation_type: WikiRelationType
authority: WikiRelationAuthority
source_page_id: string
target_page_id: string
```

No separate `authority_source` field is exposed. The authority and its
relation-type-specific mechanical basis are static application contract
metadata, not official source provenance.

`WikiNeighborDirection` is closed to:

```text
parent
child
previous_band
next_band
```

`WikiNeighborView`:

```text
page_id: string
page_type: WikiPageType
title: string
relation_type: WikiRelationType
direction: WikiNeighborDirection
```

`WikiPageDetail`:

```text
wiki_version: string
navigation_version: string
page: WikiPageSummary
breadcrumbs: array[WikiBreadcrumb]
knowledge: array[WikiKnowledgeProjection]
children: array[WikiPageSummary]
relations: array[WikiRelationView]
neighbors: array[WikiNeighborView]
```

`knowledge` has length zero for root/section pages and exactly one otherwise.
Children use sibling order.

`WikiPageDetail.relations` contains all and only canonical relations incident
to the current page. A relation is included exactly when:

```text
relation.source_page_id == current page_id
OR
relation.target_page_id == current page_id
```

Each canonical relation appears exactly once and retains its canonical
source/target orientation. The one normalized undirected `adjacent_band` edge
MUST NOT be duplicated as two directed objects. Membership is obtained by
filtering the globally ordered canonical ledger, so page-detail relations keep
the frozen order: `contains` before `adjacent_band`, then canonical full-page
order of source, then canonical full-page order of target.

For the Task Response criterion page, incident relations include Assessment
Criteria → Task Response and Task Response → each of its ten band pages. For
Task Response Band 7, they include Task Response → Task Response Band 7,
Task Response Band 6 → Task Response Band 7, and Task Response Band 7 → Task
Response Band 8. Boundary bands omit the nonexistent previous or next edge.

`relations` and `neighbors` have different responsibilities:

```text
relations = raw canonical topology edges incident to the current page
neighbors = navigation-oriented projection derived from those incident edges
```

For Task Response Band 7, the three raw relations above project to parent →
Task Response, previous_band → Band 6, and next_band → Band 8. Neighbor
directions remain `parent`, `child`, `previous_band`, and `next_band`.
Neighbors are ordered parent, children, previous band, next band, omitting
directions that do not apply. This projection MUST NOT reinterpret
`adjacent_band` as recommended progression, prerequisite, improvement path, or
Planner output.

`WikiIndexResponse`:

```text
wiki_version: string
navigation_version: string
root_page_id: string
pages: array[WikiPageSummary]
```

`pages` contains all 58 pages exactly once in the depth-first preorder frozen
in section 9.

The API MUST NOT expose filesystem paths, internal hashes, rubric compatibility
hashes, private learner/planning state, provider prompts, or chain-of-thought.

### 12.2 Error semantics

Wiki errors use the existing safe envelope:

```text
{"error": {"code": "...", "message": "...", "fields": [...]}}
```

The frozen mappings are:

| Condition | HTTP status | Error code |
| --- | ---: | --- |
| syntactically invalid path/query input | 422 | `request_invalid` |
| empty normalized `q` | 400 | `wiki_lookup_invalid` |
| ambiguous normalized lookup | 400 | `wiki_lookup_ambiguous` |
| unknown valid page ID or no lookup match | 404 | `wiki_page_not_found` |
| invalid registry, topology, ownership, relation, or provenance | 503 | `wiki_unavailable` |

Messages MUST be safe and MUST NOT include exception text, registry internals,
filesystem paths, hashes, or provider data. Registry integrity SHOULD fail at
application assembly. If an integrity failure reaches a request boundary, the
API returns only `wiki_unavailable`; it MUST NOT return fabricated or partial
Wiki content.

## 13. Frontend contract

The canonical Web routes are:

```text
/knowledge
/knowledge/[pageId]
```

`/knowledge` presents the root/index hierarchy. `/knowledge/[pageId]` presents
the canonical detail response for that page. The frontend is a presentation
client of the FastAPI Wiki contract; it MUST NOT duplicate the registry,
Knowledge statements, ownership, provenance, relation ledger, or lookup logic
in browser code.

The UI MAY provide Chinese-first interface labels and explanatory chrome. It
may display canonical Knowledge statements, provenance, breadcrumbs, children,
and adjacent descriptor navigation. New Chinese factual paraphrases are not
authorized by this contract. Canonical IDs may appear in URL segments and
developer diagnostics but SHOULD NOT be rendered as learner-facing content.

The UI must preserve keyboard navigation, visible focus, semantic heading and
list structure, meaningful link text, and safe external source links. Browser
state is not authoritative.

## 14. Citation-to-Wiki bridge and provenance

The only canonical guidance bridge is:

```text
GroundedGuidanceItem.knowledge_ids
        ↓
knowledge_id
        ↓
exact primary-page reverse lookup
        ↓
/knowledge/{page_id}
```

The bridge MUST NOT use `source_id` alone because one source supports many
KnowledgeUnits. Unknown or ambiguously owned Knowledge IDs fail closed. The
bridge changes discoverability only and MUST NOT alter Phase 9 retrieval order,
result membership, learner guidance, practice generation, scoring, or Planner
authority.

Wiki provenance projects directly from each owned KnowledgeUnit:

```text
KnowledgeUnit
    ↓ declared KnowledgeSourceRef
KnowledgeSource
```

The Wiki has no source identity of its own. `WikiSourceProjection` joins the
canonical source reference and canonical source registry without rewriting
either. Each Knowledge projection preserves source-reference declaration
order. Exact duplicate display projections are deduplicated by the tuple:

```text
(source_id, locator, page, section)
```

Deduplication preserves the first occurrence. Different locators or page/
section metadata remain distinct. No URL-only, source-only, or title-only
deduplication is permitted.

## 15. Integrity validation contract

The future validator MUST validate the complete static registry and fail closed
for at least:

- duplicate, malformed, extra, or missing page IDs;
- invalid page types or Wiki/navigation version mismatch;
- a page count other than 58;
- unknown Knowledge IDs or Knowledge version mismatch;
- missing, duplicate, secondary, or category-incompatible primary ownership;
- ownership coverage other than exactly 54 of 54 canonical KnowledgeUnits;
- unknown parents, prohibited multiple parents, or a root with a parent;
- additional roots, orphans, cycles, self-edges, unreachable pages, or
  duplicate parent-child edges;
- incorrect sibling or full-index ordering;
- unknown relation endpoints, illegal relation types, self-relations, or
  duplicate canonical relations;
- unknown `WikiRelationAuthority`, authority other than
  `application_structural`, or relation type/authority mismatch;
- a relation carrying unsupported semantic/source/provider authority;
- a relation carrying prohibited persisted free-text semantic rationale;
- reversed, nonconsecutive, or cross-criterion adjacent-band relations;
- a `contains` count other than 57 or `adjacent_band` count other than 36;
- a canonical relation count other than 93, or any of the 93 relations lacking
  `authority = application_structural`;
- title, normalized title, alias, or canonical identity collision;
- empty-string, implicit, generated, or ambiguous alias entries;
- unresolved source references or altered source identity/provenance;
- any canonical page that is not reachable from the root;
- any canonical KnowledgeUnit that is not reachable through its primary page.

Validation is deterministic, provider-free, network-independent, and complete;
it must not repair, guess, omit, or partially serve invalid content.

## 16. Phase 10 Eval extension expectations

P11-12 must extend the existing deterministic Phase 10 Eval architecture. It
must not introduce a separate Wiki Eval framework or require an LLM judge.

Required future Eval coverage includes:

- exact Knowledge ID to canonical page resolution;
- 54/54 primary ownership coverage and uniqueness;
- the 58-page topology, root, reachability, relation, and ordering invariants;
- all 93 relation authority values and the prohibition on persisted rationale;
- exact incident-relation membership and relation-to-neighbor projection;
- deterministic page, relation, neighbor, breadcrumb, and lookup results;
- unknown page and unknown Knowledge failures;
- preservation of Knowledge source references and canonical source identity;
- read-only API authority and safe error behavior;
- guidance `knowledge_ids` to canonical Wiki page mapping;
- proof that Wiki output does not change scoring, Planner, Memory, Agent, or
  adaptive retrieval authority.

VETO-class examples include:

```text
unknown Knowledge presented as grounded
relation references a nonexistent page
Wiki loses or rewrites Knowledge provenance
Wiki introduces unsupported factual content
Wiki changes scoring authority
Wiki overrides Planner or practice-target authority
Wiki changes existing adaptive retrieval results
mutation endpoint or provider-owned Wiki identity is exposed
```

## 17. Explicit non-goals

P11-02 does not authorize:

```text
Vector DB
embeddings
semantic search
RAG
GraphRAG
LangChain
LangGraph
Neo4j
runtime crawling
runtime web search
automatic ingestion
LLM-created pages
LLM-created relations
new database tables
migrations
new external dependencies
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
Speaking
Reading
Listening
authentication
payments
```

## 18. Current Phase 11 implementation status

P11-02 was frozen and externally approved before implementation began. The
following block records current Phase 11 implementation status only; it is not
part of the semantic completion condition for the P11-02 design contract.

```text
P11-00 = COMPLETE
Phase 11 Graph Review = APPROVED
P11-01 = COMPLETE
P11-01 External Audit Review = APPROVED
P11-02 = COMPLETE
Phase 11 External Design Review = APPROVED
P11-03 = COMPLETE
P11-04 = COMPLETE
P11-05 = COMPLETE
P11-06 = COMPLETE
P11-07 = COMPLETE
P11-08 = COMPLETE
Phase 11 Milestone Review = APPROVED
P11-09 = COMPLETE
P11-10 = COMPLETE
P11-11 = COMPLETE
P11-12 = COMPLETE
P11-13 = COMPLETE
P11-14 = COMPLETE
P11-15 = COMPLETE
P11-16 = INTERNAL_AUDIT_COMPLETE
Phase 11 External Implementation Review = CHANGES_REQUESTED
Phase 11 PR Validation = BLOCKED_BY_EXTERNAL_IMPLEMENTATION_REVIEW
Merge Authorization = BLOCKED
Phase 11 = NOT COMPLETE
```

Later nodes remain governed by the Phase 11 dependency graph.
