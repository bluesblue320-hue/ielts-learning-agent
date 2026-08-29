# Phase 11 — Structured Wiki Knowledge v1

## Document Status

**BATCH C ACTIVE — MILESTONE REVIEW APPROVED; P11-13 ACTIVE**

Repository:

```text
bluesblue320-hue/ielts-learning-agent
```

Proposed branch:

```text
phase/11-writing-wiki-knowledge-v1
```

Base:

```text
master
```

Phase 10 merge baseline:

```text
PR #14
merge commit: c7a5f991df9c556408295d01194f1f17c13653b5
```

Current phase state:

```text
Phase 10 = COMPLETE
PR #14 = MERGED
Phase 11 = STARTED
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
P11-13 = ACTIVE
P11-14 onward = BLOCKED_BY_DEPENDENCY
```

Scope:

```text
IELTS Writing Task 2 only
```

Primary goal:

```text
Transform the existing flat, source-backed Phase 9 Writing Knowledge snapshot
into a deterministic, versioned, relation-aware Wiki Knowledge layer that can
be browsed, validated, linked from existing product surfaces, and later serve
as a clean substrate for a separately authorized retrieval/RAG phase.
```

Phase 11 is a **knowledge-organization phase**.

It is not a semantic-search or RAG phase.

---

# 1. Upstream Frozen Contracts

Phase 11 inherits and preserves the existing production contracts.

Frozen:

```text
writing-task2-v1
ielts-writing-knowledge-v1
writing-knowledge-structured-v1
writing-grounded-guidance-v1
writing-practice-generation-v2
writing-memory-v1
writing-progress-v1
writing-practice-gap-memory-v2
Core Learning Agent v1
writing-eval-calibration-v1
```

Phase 11 must not silently change their semantics.

The existing Phase 9 Knowledge layer remains the authority for source-backed IELTS claims.

```text
KnowledgeUnit
=
atomic source-backed IELTS claim
```

Phase 11 adds:

```text
WikiPage
=
application-owned organization of KnowledgeUnits

WikiRelation
=
explicit application-owned relationship between WikiPages

Wiki Navigation
=
deterministic traversal over pages and relations
```

The Wiki does not replace KnowledgeUnit.

---

# 2. Current Baseline

Phase 9 currently exposes a flat static Writing Task 2 Knowledge snapshot.

Current canonical Knowledge consists of:

```text
4 assessment criterion units
40 criterion × integer-band guidance units
3 Writing Task 2 rule units
7 Task 2 task-type units
--------------------------------
54 KnowledgeUnits
```

Each KnowledgeUnit already has:

```text
knowledge_id
knowledge_version
category
criterion where applicable
descriptor_band where applicable
task_type where applicable
statement
source_refs
```

Phase 11 starts from these existing objects.

It must not duplicate them into another authoritative claim store.

---

# 3. Target Architecture

```text
Official IELTS Sources
        |
        v
Phase 9 KnowledgeSource
        |
        v
Phase 9 KnowledgeUnit
atomic grounded claims
        |
        v
+-----------------------------+
| Phase 11 Wiki Knowledge v1  |
+-----------------------------+
        |
        +--> WikiPage Registry
        |
        +--> WikiRelation Ledger
        |
        +--> Integrity Validator
        |
        +--> Deterministic Index
        |
        +--> Navigation Service
        |
        +--> Read-only API
        |
        +--> Web Wiki Experience
        |
        v
Existing Guidance / Citation UX
        |
        v
future separately authorized
retrieval / RAG phase
```

The conceptual dependency direction is:

```text
Sources
   ↓
KnowledgeUnit
   ↓
WikiPage
   ↓
WikiRelation
   ↓
Navigation / Presentation
```

Never reverse this authority.

Wiki page text must not become authoritative evidence for changing:

```text
Writing scores
Planner decisions
Learner state
KnowledgeUnit semantics
```

---

# 4. Wiki v1 Versions

Proposed version identifiers:

```text
ielts-writing-wiki-v1
writing-wiki-navigation-v1
```

Exact identifiers are frozen by P11-02.

Changing only presentation wording does not automatically require a Wiki semantic version change.

Changes to:

```text
page identity
page grouping semantics
relation meaning
relation direction
navigation semantics
KnowledgeUnit ownership mapping
```

require explicit compatibility review and may require a new Wiki version.

---

# 5. WikiPage Concept

Conceptual model:

```python
WikiPage(
    page_id="writing-wiki-task-response",
    wiki_version="ielts-writing-wiki-v1",
    page_type="criterion",
    title="Task Response",
    knowledge_ids=(
        "writing-task-response-criterion",
        ...
    ),
    aliases=(...),
)
```

Important distinction:

```text
WikiPage metadata
!=
new IELTS factual authority
```

A page organizes existing KnowledgeUnits.

The authority boundary is normative:

```text
WikiPage MUST NOT introduce new normative IELTS factual claims.

WikiPage content may contain only:

1. deterministic composition or projection of mapped existing KnowledgeUnits;
2. application-owned navigational or presentation metadata that does not add
   new IELTS factual meaning.
```

Wiki titles, aliases, breadcrumbs, grouping labels, and navigation labels are
application-owned metadata. They are not authoritative IELTS claims and must
not be presented as source-backed facts.

Any new IELTS factual meaning MUST first be introduced as a valid source-backed
KnowledgeUnit under the existing Phase 9 Knowledge authority before the Wiki
may expose it. Wiki assembly must fail closed when it would require unsupported
factual content. Phase 11 does not change `ielts-writing-knowledge-v1` and this
Graph repair adds no KnowledgeUnits.

---

# 6. Proposed Page Classes

The exact closed enum is frozen by P11-02.

Expected minimum classes:

```text
index
criterion
band_descriptor
task_rule
task_type
```

Possible hierarchy:

```text
Writing Task 2
│
├── Assessment Criteria
│   │
│   ├── Task Response
│   │   ├── Band 0
│   │   ├── Band 1
│   │   ├── ...
│   │   └── Band 9
│   │
│   ├── Coherence and Cohesion
│   │   └── Band 0 ... Band 9
│   │
│   ├── Lexical Resource
│   │   └── Band 0 ... Band 9
│   │
│   └── Grammatical Range and Accuracy
│       └── Band 0 ... Band 9
│
├── Task Rules
│   ├── Minimum 250 words
│   ├── Connected text
│   └── Answer the prompt directly
│
└── Task Types
    ├── Opinion
    ├── Discussion
    ├── Multi-part
    ├── Multi-part Opinion
    ├── Advantage / Disadvantage
    ├── Positive / Negative
    └── Cause / Solution
```

The exact page count is not frozen by this graph.

P11-02 freezes the canonical topology after P11-01 audits the existing Knowledge corpus.

---

# 7. WikiRelation Concept

Phase 11 introduces explicit relations instead of relying on implicit filename or list ordering.

Conceptual shape:

```python
WikiRelation(
    source_page_id="writing-wiki-task-response-band-6",
    relation_type="adjacent_band",
    target_page_id="writing-wiki-task-response-band-7",
    authority="structural",
    rationale="Numerically adjacent integer descriptor bands within one criterion.",
)
```

Relations must distinguish:

```text
navigation / structural relationships

from

source-backed IELTS semantic claims
```

A relation must not appear to be an official IELTS claim merely because it
exists in the Wiki graph. The `adjacent_band` example records structural
numeric adjacency only; it does not assert a pedagogical progression,
improvement path, recommendation, prerequisite, or stronger directional meaning
from Band 6 to Band 7.

Structural/navigation relations may be application-owned only when they are
derived deterministically from already-authorized canonical metadata.
Illustrative structural concepts include:

```text
contains
parent_of
child_of
adjacent_band
```

Semantic relations can themselves introduce factual or pedagogical meaning.
Illustrative semantic concepts include:

```text
related_to
applies_to
supports
improves
prerequisite_of
```

These names are illustrative only. The Wiki layer MUST NOT freely invent a
semantic relation. Any semantic relation MUST be backed by existing authorized
Knowledge evidence or explicit source-backed justification frozen by P11-02.
Unsupported semantic relations fail closed.

P11-02 must freeze:

```text
allowed relation types
structural vs semantic classification
directionality
symmetry rules
inverse relation behavior
authority classification
authority source
required rationale
ordering behavior
cycle policy
validation rules
```

before implementation. There is no runtime LLM relation inference, automatic
graph enrichment, or GraphRAG.

---

# 8. Core Integrity Rules

Phase 11 must fail closed on invalid Wiki topology.

At minimum:

```text
all page_ids unique
all referenced Knowledge IDs resolve
all relation source pages resolve
all relation target pages resolve
no self-relations
no duplicate canonical relations
relation types belong to closed enum
page types belong to closed enum
Wiki versions are consistent
deterministic ordering is preserved
```

The canonical Writing Wiki should also prove:

```text
all 54 Phase 9 KnowledgeUnits are reachable through the Wiki
```

unless P11-02 explicitly records a reviewed exception.

No source-backed KnowledgeUnit may silently disappear simply because it is inconvenient to organize.

P11-02 must freeze KnowledgeUnit-to-WikiPage multiplicity and canonical reverse
lookup. The Phase 11 v1 mapping model is:

```text
KnowledgeUnit
    ↓
exactly one primary canonical WikiPage owner
```

Additional WikiPages may reference the same KnowledgeUnit only as secondary
references if P11-02 explicitly allows them. Secondary presentation references
do not change canonical ownership.

P11-02 must freeze at minimum:

```text
primary_page_id semantics
allowed secondary references
canonical reverse lookup behavior
deduplication
deterministic ordering
ambiguity handling
```

Resolving a Wiki page from a Knowledge ID must always return one deterministic
canonical primary page or fail closed. Any separately exposed secondary
references must be deduplicated and deterministically ordered.

For hierarchical relations, P11-02 must define whether:

```text
single-root reachability
acyclicity
single/multiple parent policy
```

are required.

---

# 9. Authority Boundary

Phase 11 Wiki owns:

```text
knowledge organization
page identity
page grouping
navigation relationships
Wiki lookup
Wiki presentation
```

It does not own:

```text
Writing scoring
rubric semantics
learner state
Memory chronology
Planner target selection
practice target selection
Agent action authority
provider output
LearningUpdate ordering
evaluation persistence
```

Knowledge authority remains:

```text
Official source
    ↓
KnowledgeSourceRef
    ↓
KnowledgeUnit
```

Wiki authority is:

```text
KnowledgeUnit
    ↓
application-owned organization
    ↓
WikiPage / WikiRelation
```

---

# 10. Runtime Policy

Wiki v1 remains:

```text
Git-versioned
static
deterministic
provider-free
network-independent
```

Runtime behavior must not:

```text
search the internet
crawl IELTS websites
generate new Wiki pages with an LLM
generate new relations with an LLM
automatically edit Knowledge
automatically rewrite Wiki topology
```

---

# 11. Explicit Non-goals

Phase 11 MUST NOT introduce:

```text
Vector Database
Embedding
semantic similarity search
generic RAG framework
LangChain
LangGraph
GraphRAG
knowledge-graph database
Neo4j
runtime web search
runtime crawling
automatic web ingestion
LLM-generated Wiki topology
LLM-generated authoritative Knowledge
multi-agent runtime
new Writing evaluator semantics
writing-task2-v2
Planner semantic changes
Memory semantic changes
Agent authority expansion
Speaking
Reading
Listening
authentication
payments
```

Phase 11 should not introduce a PostgreSQL Wiki persistence layer unless the frozen design review finds a concrete requirement that cannot be satisfied by the Git-versioned static model.

Default:

```text
no migration
no new database table
no new external dependency
```

---

# 12. Future RAG Boundary

Phase 11 may make future retrieval cleaner.

It must not implement it.

Future direction:

```text
Phase 9
atomic KnowledgeUnits
        ↓
Phase 11
Wiki topology
        ↓
Future phase
retrieval / hybrid retrieval / RAG
```

A later phase may decide whether retrieval operates over:

```text
KnowledgeUnits
WikiPages
relations
hybrid representations
```

Phase 11 must not pre-decide the vector-storage implementation.

---

# 13. Dependency Graph

```text
START
  |
  v
P11-00 Phase 11 Kickoff / Phase Status Sync / Graph Establishment [COMPLETE]
  |
  v
Phase 11 Graph Review [APPROVED]
  |
  v
P11-01 Existing Knowledge & Product Surface Audit [COMPLETE]
  |
  v
P11-01 External Audit Review [APPROVED]
  |
  v
P11-02 Wiki Knowledge Contract Freeze [COMPLETE]
  |
  v
Phase 11 External Design Review [APPROVED]
  |
  v
P11-03 Wiki Schemas [COMPLETE]
  |
  v
P11-04 Canonical Wiki Page Registry [COMPLETE]
  |
  v
P11-05 Wiki Relation Ledger [COMPLETE]
  |
  v
P11-06 Wiki Integrity Validator [COMPLETE]
  |
  v
P11-07 Deterministic Wiki Navigation / Lookup Service [COMPLETE]
  |
  v
P11-08 Read-only Wiki API [COMPLETE]
  |
  v
Phase 11 Milestone Review [APPROVED]
  |
  v
P11-09 Typed Web Wiki Client [COMPLETE]
  |
  v
P11-10 Wiki Index + Page Detail Experience [COMPLETE]
  |
  v
P11-11 Existing Citation -> Wiki Navigation Bridge [COMPLETE]
  |
  v
P11-12 Phase 10 Eval Harness Wiki Extension [COMPLETE]
  |
  v
P11-13 Wiki Browser E2E / Integration Regression [ACTIVE]
  |
  v
P11-14 Documentation & Architecture Synchronization
  |
  v
P11-15 Full Phase 1-11 Regression Validation
  |
  v
P11-16 Internal Audit
  |
  v
Phase 11 External Implementation Review
  |
  v
Phase 11 PR Validation
  |
  v
Merge Authorization
  |
  v
STOP
```

---

# P11-00 — Phase 11 Kickoff / Phase Status Sync / Graph Establishment — COMPLETE

## Goal

Establish a truthful post-Phase-10 repository baseline and create the formal Phase 11 graph.

## Required work

Create:

```text
docs/PHASE11_GRAPH.md
```

Create branch:

```text
phase/11-writing-wiki-knowledge-v1
```

Synchronize stale Phase 10 status in at least:

```text
AGENTS.md
README.md
docs/ARCHITECTURE.md
```

Inspect whether:

```text
docs/PHASE10_GRAPH.md
docs/PHASE10_AUDIT.md
```

also require final post-merge status synchronization.

Record:

```text
Phase 10 = COMPLETE
PR #14 = MERGED
Phase 11 = GRAPH_REVIEW_PENDING
```

## Restrictions

Documentation only.

Do not implement Wiki runtime code.

## Acceptance

Repository documentation no longer claims that Phase 10 is unmerged.

Phase 11 graph exists and accurately declares its boundaries.

## Status

```text
COMPLETE
```

---

# GRAPH REVIEW — HARD STOP

Current status:

```text
APPROVED
```

External review must verify:

```text
Phase 11 actually addresses a meaningful knowledge-organization gap
Wiki is not disguised RAG
Knowledge and Wiki authority are separated
Phase 9 provenance is preserved
scope is Writing Task 2 only
no unnecessary persistence or framework is introduced
```

No P11-01 work may start until Graph Review is APPROVED.

---

# P11-01 — Existing Knowledge & Product Surface Audit — COMPLETE

## Goal

Audit the actual Phase 9 implementation before freezing Wiki semantics.

Inspect at minimum:

```text
app/knowledge/
app/schemas/knowledge.py
grounded guidance service
practice-generation Knowledge context
API Knowledge responses
Web citation rendering
Phase 10 grounding evaluators
Knowledge tests
```

Inventory:

```text
all canonical Knowledge IDs
categories
criterion/band mappings
task types
source references
retrieval ordering
existing UI citation behavior
existing tests and invariants
```

Produce:

```text
docs/PHASE11_AUDIT.md
```

Status:

```text
COMPLETE
```

---

# P11-01 EXTERNAL AUDIT REVIEW — HARD STOP

Review whether the audit describes actual code rather than intended architecture.

No Wiki contract may be frozen from assumptions.

Current status:

```text
APPROVED
```

---

# P11-02 — Wiki Knowledge Contract Freeze — COMPLETE

Current status:

```text
COMPLETE
```

## Goal

Freeze the exact semantic model before implementation.

Create:

```text
docs/WIKI_KNOWLEDGE_POLICY.md
```

Freeze at minimum:

```text
Wiki version
navigation version
page schema semantics
page types
relation schema semantics
relation types
structural vs semantic relation classification
relation directionality
relation symmetry and inverse behavior
relation authority classification
relation authority source
KnowledgeUnit mapping rules
primary canonical ownership and allowed secondary references
canonical reverse lookup, deduplication, ordering, and ambiguity behavior
root/reachability policy
cycle policy
ordering policy
alias policy
lookup/search semantics
versioning rules
public API boundary
frontend boundary
failure behavior
```

Also freeze exact canonical v1 topology expectations.

No implementation should invent additional semantics after this point.

---

# EXTERNAL DESIGN REVIEW — HARD STOP

Current status:

```text
APPROVED
```

The review must explicitly approve:

```text
WikiPage vs KnowledgeUnit boundary
WikiRelation authority boundary
topology invariants
public read-only surface
Phase 9 compatibility
future-RAG separation
```

P11-03 may not start without approval.

---

# P11-03 — Wiki Schemas — COMPLETE

Current status:

```text
COMPLETE
```

Implement strict application-owned schemas for:

```text
WikiPage
WikiRelation
WikiPageType
WikiRelationType
WikiRelationAuthority
WikiPageSummary / Detail response
WikiNeighbor / navigation response
```

Exact names follow P11-02.

Schemas must fail closed on malformed versions, IDs, enum values, and structural fields.

No database model.

---

# P11-04 — Canonical Wiki Page Registry — COMPLETE

Build the static canonical Writing Task 2 Wiki page registry.

Pages must be:

```text
stable-ID
versioned
reviewable
Git-controlled
deterministically ordered
```

Map Phase 9 Knowledge IDs to the appropriate pages.

Every canonical KnowledgeUnit must have exactly one `primary_page_id` owner.
Any secondary references must be explicitly allowed by the frozen policy,
deduplicated, deterministically ordered, and must not change canonical reverse
lookup.

Do not duplicate KnowledgeUnit factual content as a second source of truth.

Tests must prove complete canonical mapping.

---

# P11-05 — Wiki Relation Ledger — COMPLETE

Create the explicit reviewed relation ledger.

Every relation must declare at minimum:

```text
source page
relation type
target page
authority classification
authority source where required
rationale where required
```

For Wiki v1, the frozen authority is `application_structural`; its basis is
mechanically derived from the frozen structural policy, no separate authority
source is stored, and structural relation rationale is not required or stored.

No relationship may be inferred at runtime by an LLM or added through automatic
graph enrichment. Semantic relations without the evidence required by P11-02
must fail closed.

Tests must cover:

```text
duplicate edge
self-edge
unknown endpoint
unknown relation type
illegal direction
illegal symmetry
illegal inverse behavior
unsupported semantic relation
unknown or non-application structural authority
prohibited persisted free-text semantic rationale
```

---

# P11-06 — Wiki Integrity Validator — COMPLETE

Implement deterministic full-snapshot validation.

It must fail closed for:

```text
duplicate page IDs
unknown Knowledge IDs
unmapped required KnowledgeUnits
missing or duplicate primary KnowledgeUnit ownership
illegal, duplicate, or ambiguously ordered secondary references
unknown relation endpoints
duplicate relations
invalid page types
invalid relation types
version mismatch
forbidden topology
unreachable required pages
```

Validation should run during tests and, where appropriate, module initialization or explicit registry validation.

---

# P11-07 — Deterministic Wiki Navigation / Lookup Service — COMPLETE

Implement provider-free deterministic navigation.

Required conceptual operations:

```text
list pages
get page by canonical ID
resolve page alias
list page neighbors
walk structural children
resolve the canonical primary Wiki page from Knowledge ID
list explicitly allowed secondary Wiki references for a Knowledge ID
```

Optional deterministic text lookup may support:

```text
canonical ID
title
alias
exact token
bounded prefix matching
```

only if the deterministic lookup semantics were explicitly frozen.

No:

```text
embedding search
semantic ranking
LLM ranking
vector similarity
```

Identical normalized input must produce identical ordered output.

---

# P11-08 — Read-only Wiki API — COMPLETE

Expose a bounded read-only API.

Exact routes are frozen in P11-02.

Conceptual examples:

```text
GET /knowledge/writing/wiki
GET /knowledge/writing/wiki/{page_id}
```

Potential query capability:

```text
?q=
```

only if the deterministic lookup semantics were explicitly frozen.

API must expose:

```text
page identity
page type
mapped Knowledge
provenance
structural navigation
relations
```

It must not expose unsafe internal implementation data.

No write endpoint.

No admin mutation endpoint.

---

# PHASE 11 MILESTONE REVIEW — HARD STOP

Current status:

```text
APPROVED
```

Before frontend integration verify:

```text
canonical topology validates
all required Phase 9 Knowledge remains reachable
navigation is deterministic
API is read-only
no scoring/planner/memory semantics changed
no RAG capability slipped into scope
```

---

# P11-09 — Typed Web Wiki Client — COMPLETE

Current status:

```text
COMPLETE
```

Add typed client support for the frozen Wiki API.

Requirements:

```text
strict TypeScript types
centralized API client
safe error handling
no browser-side source of truth
```

---

# P11-10 — Wiki Index + Page Detail Experience — COMPLETE

Current status:

```text
COMPLETE
```

Add a Chinese-first Wiki browsing experience.

Conceptual route:

```text
/knowledge
```

or the exact path frozen in P11-02.

The UI should support:

```text
Wiki overview
assessment criteria navigation
band navigation
Writing rules
Task 2 task types
related pages
source provenance
back/breadcrumb navigation
loading
empty
error
retry
responsive layout
keyboard accessibility
```

The frontend is presentation only.

---

# P11-11 — Existing Citation -> Wiki Navigation Bridge — COMPLETE

Current status:

```text
COMPLETE
```

Existing grounded guidance and Knowledge citations may link into corresponding Wiki pages.

Important:

```text
citation -> Wiki navigation
```

does not mean:

```text
Wiki -> changes retrieval decision
```

Phase 9 guidance retrieval and practice-generation selection semantics remain frozen.

This node changes discoverability/presentation only.

---

# P11-12 — Phase 10 Eval Harness Wiki Extension — COMPLETE

Current status:

```text
COMPLETE
```

Extend deterministic Eval coverage rather than creating a parallel ad-hoc test architecture.

Add Wiki-specific regression cases for:

```text
page resolution
Knowledge mapping
relation integrity
deterministic ordering
unknown ID fail-closed behavior
provenance preservation
API authority
citation -> Wiki mapping
```

Veto-class examples:

```text
unknown Knowledge presented as grounded
relation points to nonexistent page
source provenance disappears during Wiki assembly
Wiki changes scoring authority
Wiki silently overrides Planner ownership
```

No LLM judge is required.

---

# P11-13 — Wiki Browser E2E / Integration Regression — ACTIVE

Current status:

```text
ACTIVE
```

Add browser-level validation of representative Wiki flows.

At minimum verify:

```text
open Wiki
navigate to criterion
open descriptor band
inspect provenance
follow related navigation
return through breadcrumb
open Wiki page from an existing citation
```

Use isolated deterministic application state.

No live provider.

---

# P11-14 — Documentation & Architecture Synchronization

Update as required:

```text
README.md
AGENTS.md
docs/ARCHITECTURE.md
docs/API.md
docs/LOCAL_DEVELOPMENT.md
docs/WIKI_KNOWLEDGE_POLICY.md
docs/PHASE11_GRAPH.md
docs/PHASE11_AUDIT.md
```

Documentation must distinguish:

```text
Learning Memory
IELTS Knowledge
Wiki Knowledge
future RAG
```

These must not be described as interchangeable concepts.

---

# P11-15 — Full Phase 1-11 Regression Validation

Run the complete relevant validation matrix.

Expected classes:

```text
backend unit/API tests
isolated PostgreSQL tests
Phase 10 deterministic Eval gate
frontend lint
frontend typecheck
frontend unit tests
frontend production build
Playwright E2E
migration-head verification
forbidden-scope scan
secret scan
git diff --check
```

Phase 11 should require no live provider credential.

---

# P11-16 — Internal Audit

Produce final implementation evidence.

Record:

```text
implemented topology
page count
relation count
Knowledge coverage
validation results
test counts
API surface
frontend surface
known limitations
future work
forbidden-scope verification
commit range
```

Status after successful audit:

```text
INTERNAL_AUDIT_COMPLETE
```

Do not mark Phase 11 COMPLETE yet.

---

# EXTERNAL IMPLEMENTATION REVIEW — HARD STOP

External review must check actual implementation against:

```text
PHASE11_GRAPH.md
WIKI_KNOWLEDGE_POLICY.md
IELTS_KNOWLEDGE_POLICY.md
Phase 9 frozen behavior
Phase 10 Eval contracts
```

A passing test suite alone is insufficient.

---

# PR VALIDATION

Open a Phase 11 PR only after External Implementation Review approval.

Required:

```text
PR CI PASS
reviewed diff
scope verification
no unexpected migration
no new forbidden dependency
no Phase 12 implementation
```

---

# MERGE AUTHORIZATION — HARD STOP

Do not merge automatically.

Explicit merge authorization is required.

After merge:

```text
Phase 11 = COMPLETE
```

Then STOP.

Do not begin the future RAG phase automatically.

---

# Phase 11 Success Definition

Phase 11 succeeds when the project can prove:

```text
Phase 9 source-backed Knowledge
        ↓
complete Wiki mapping
        ↓
explicit reviewed topology
        ↓
deterministic navigation
        ↓
read-only product API
        ↓
browseable Wiki UX
        ↓
preserved provenance
        ↓
deterministic regression coverage
```

while preserving:

```text
scoring authority
learner-state authority
Memory authority
Planner authority
Agent authority
Phase 9 Knowledge semantics
```

and without introducing:

```text
RAG
Vector DB
Embedding
semantic search
runtime crawling
multi-agent architecture
```

The architectural result should be:

```text
Learner-specific information
        |
        +--> State
        +--> Memory
        +--> Planner
        |
        v
Core Learning Agent

Learner-independent IELTS information
        |
        v
KnowledgeUnit
        |
        v
Structured Wiki
        |
        +--> Page
        +--> Relation
        +--> Navigation
        +--> Provenance
        |
        v
Guidance / Practice / Learner browsing
```
