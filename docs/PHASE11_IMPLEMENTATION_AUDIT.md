# Phase 11 Structured Wiki Knowledge v1 — Implementation Audit

## Audit result

Phase 11 implementation through P11-15 satisfies the frozen Wiki contract and
the P11-16 internal audit gate. This is internal implementation evidence, not
external approval and not merge authorization.

```text
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

Audit date: 2026-08-29

## Repository evidence

```text
repository = bluesblue320-hue/ielts-learning-agent
branch = phase/11-writing-wiki-knowledge-v1
base/master commit = c7a5f991df9c556408295d01194f1f17c13653b5
reviewed Batch C input head = 73b846b6
Phase 11 pre-audit range = 3a13ae5..70bae7f
runtime implementation range = ece3bde..8a2fd41
Batch C pre-audit range = baf132a..70bae7f
```

The commit containing this audit follows the recorded pre-audit range and
cannot self-reference its own commit ID. The reviewed input head is an ancestor
of the audited branch.

## Frozen versions and topology proof

```text
Wiki version = ielts-writing-wiki-v1
navigation version = writing-wiki-navigation-v1
Knowledge version = ielts-writing-knowledge-v1
pages = 58
KnowledgeUnits = 54
owned Knowledge IDs = 54
unique owned Knowledge IDs = 54
Knowledge ownership coverage = 54/54
contains relations = 57
adjacent_band relations = 36
total relations = 93
relation authority = application_structural (93/93)
```

The validated singleton snapshot, canonical registry, relation ledger, and
deterministic Eval assertions produced these counts directly. Every Knowledge
ID has exactly one primary page owner. Registry validation fails closed for bad
page identity, topology, ownership, relation type/authority, or provenance.
Preorder, breadcrumbs, exact ID/title/alias lookup, incident relations,
neighbors, and Knowledge-to-page reverse lookup are deterministic.

## Implemented surfaces

The read-only FastAPI surface is:

```text
GET /knowledge/writing/wiki
GET /knowledge/writing/wiki?q={exact_id_title_or_alias}
GET /knowledge/writing/wiki/{page_id}
```

The index exposes canonical preorder. Detail responses contain breadcrumbs,
owned Knowledge and source provenance, children, incident relations, and
deterministic neighbors. Safe invalid, ambiguous, missing, and unavailable
states use the existing API error envelope. There is no Wiki mutation route.

The Chinese-first Web surface is:

```text
/knowledge
/knowledge/[pageId]
```

The browser is a typed presentation client of FastAPI and does not duplicate
the 58-page registry or 54-entry ownership map. It provides hierarchy,
breadcrumbs, source links, child navigation, and explicitly structural
adjacent-band navigation with loading, empty, failure, and retry states.

Grounded guidance preserves its frozen retrieval result and adds only a
server-resolved `wiki_pages` projection for each existing `knowledge_id`.
Multiple IDs preserve order; identical resulting pages are deduplicated by
first occurrence; unknown IDs fail closed. The dashboard uses the returned
canonical page ID for internal “查看知识页” navigation. It does not infer from
source identity, title, locator, or semantic similarity.

## Eval extension and authority proof

The existing Phase 10 Eval architecture now includes `wiki_knowledge` evidence
and deterministic findings. It verifies all frozen counts and versions,
identity syntax, preorder, breadcrumbs, incident relations, and neighbor
projection independently derived from canonical pages and relations, exact
title lookup, safe unknown handling, provenance, API
read-only behavior, citation mapping, and unchanged guidance retrieval.

Wiki remains an organization/navigation projection over source-backed IELTS
Knowledge. It has no authority over Writing scoring, learner State, longitudinal
Memory, Planner selection, Agent behavior, practice targets, or provider
identity. No LLM judge or live provider is used by the Wiki Eval extension.

## Validation evidence

All commands used the repository's existing Python virtual environment and Web
scripts. PostgreSQL validation used an isolated temporary PostgreSQL 18 database
on localhost because the host Docker daemon was unavailable; the Wiki runtime
itself remains database-independent.

| Validation | Result |
| --- | --- |
| Full backend suite with isolated PostgreSQL | `1200 passed`, 1 existing Starlette deprecation warning, 31.17s |
| Phase 10 deterministic gate self-tests, including Wiki extension | `78 passed`, 1 existing warning |
| Canonical Phase 10 corpus | `11/11 PASS`, FAIL=0, VETO=0 |
| Frontend ESLint | PASS |
| Frontend TypeScript `--noEmit` | PASS |
| Frontend unit tests | `20 passed` |
| Frontend production build | PASS; `/knowledge` static and `/knowledge/[pageId]` dynamic routes emitted |
| Full Playwright suite | `8 passed`, including 2 Phase 11 Wiki flows |
| Phase 11 changed-Python Ruff scan | PASS |
| Python compileall | PASS |
| Alembic current/head | `0006_submission_claim_recovery (head)` |
| Alembic downgrade/upgrade | PASS: head → base → head |
| `git diff --check` for Phase 11 range | PASS |
| High-confidence secret scan of Phase 11 changed files | PASS; no matches |

An additional non-gating full-repository Ruff diagnostic reported 236 legacy
findings outside the Phase 11 change boundary. Ruff is not configured in the
repository CI or project dependencies; all Python files changed by Phase 11
pass the available Ruff scan. No legacy file was bulk-rewritten during this
bounded phase.

No live LLM provider credential was required. Live calibration was not run and
is not a Phase 11 gate.

## External implementation review repair addendum

Repair date: 2026-08-30

The initial validation table above is preserved as the original P11-16 audit
evidence. External Implementation Review subsequently identified two focused
implementation gaps and one documentation inconsistency. The repair from
reviewed head `d76bb4b7bba242798cb77ae4120ebb176487e879` makes these changes:

- Wiki Eval now derives expected neighbor semantics directly from canonical
  pages, the canonical relation ledger, and the frozen `contains` and
  `adjacent_band` orientations. It orders parent, canonical children,
  previous-band, then next-band and compares all five public semantic fields
  against `WIKI_SERVICE.neighbors()` for all 58 pages.
- A monkeypatch regression proves a stable wrong Band 7 direction is rejected
  with VETO code `wiki_neighbor_projection_mismatch`; the expected result does
  not call the service neighbor projection.
- The TypeScript client now exposes the full closed backend
  `KnowledgeAuthority` union (`official_ielts`, `official_british_council`, and
  `official_idp`) and uses it for `WikiSourceProjection.authority`.
- `WikiKnowledgeProjection.task_type` now uses the closed seven-value
  `WritingTask2TaskType` union. Typecheck covers every authority, an allowed
  task type, and a negative arbitrary-string assertion without a new
  dependency.
- The P11-14 node body now says `COMPLETE`. The Wiki policy's final section is
  explicitly a current implementation-status note, not a P11-02 semantic
  completion gate.

Refreshed repair validation used an isolated temporary PostgreSQL 18 database
because the Docker daemon remained unavailable:

| Repair validation | Result |
| --- | --- |
| Required focused backend Wiki/guidance suites | `49 passed`, 1 existing warning |
| Full backend suite with isolated PostgreSQL | `1201 passed`, 1 existing warning, 37.68s |
| Deterministic gate self-tests, including stable-wrong-neighbor mutation | `79 passed`, 1 existing warning |
| Canonical Phase 10 corpus | `11/11 PASS`, FAIL=0, VETO=0 |
| Frontend ESLint | PASS |
| Frontend TypeScript `--noEmit` | PASS |
| Frontend unit tests | `21 passed` |
| Frontend production build | PASS |
| Full Playwright suite | `8 passed`, including 2 Phase 11 Wiki flows |
| Changed-Python Ruff scan and Python compileall | PASS |
| Alembic current/head | `0006_submission_claim_recovery (head)` |
| Alembic downgrade/upgrade | PASS: head → base → head |
| Repair dependency and migration delta | NONE |
| Repair forbidden-scope additions scan | PASS; no matches |
| Repair high-confidence secret scan | PASS; no matches |
| Repair `git diff --check` | PASS |

The repair adds no migration, schema, dependency, scoring, retrieval, Planner,
Memory, Agent, or practice-target change. External Implementation Review
remains `CHANGES_REQUESTED`; only the external reviewer may approve it.

## Persistence and dependency delta

Phase 11 adds no Alembic revision and no database schema. The migration head
remains the pre-Phase-11 revision `0006_submission_claim_recovery`.

There is no Phase 11 diff in `pyproject.toml`, `web/package.json`, supported
lockfiles, or `migrations/`. No UI library, vector store, embedding runtime, or
other dependency was added.

## Forbidden-scope verification

The Phase 11 diff was checked for the prohibited scope. It introduces none of:

- vector database, embedding model, semantic similarity, generic RAG, GraphRAG,
  Neo4j, LangChain, or LangGraph;
- crawler, runtime web search, automatic ingestion, or LLM-generated Wiki
  pages/relations;
- multi-agent runtime or provider-owned Wiki identity;
- new Writing scoring semantics, Planner behavior, Memory semantics, Agent
  authority, or practice-target authority;
- Speaking, Reading, or Listening Wiki implementation;
- authentication or payments.

The only scan hits for “authentication” were pre-existing provider error codes
on already-existing lines, not a Phase 11 authentication feature. Documentation
references to future RAG are boundary statements, not implementation.

## Known limitations

- Writing Task 2 only.
- Static, Git-controlled, read-only Wiki.
- Canonical Knowledge statements are English; learner-facing Web chrome is
  Chinese-first.
- Exact normalized ID/title/alias lookup only; no semantic search.
- No vector retrieval, runtime web ingestion, or automatic corpus ingestion.
- No Wiki editing/admin UI and no user-generated Wiki content.
- Task-type pages are browse-only relative to adaptive retrieval.
- No Reading, Listening, or Speaking Wiki.
- No new persistence; topology changes require reviewed source changes and a
  compatible versioning decision.

## Future work and hard stop

External Implementation Review requested focused repairs after this initial
audit. PR validation remains blocked until the repaired implementation is
re-reviewed and explicitly approved. No PR, merge, Phase 12 work, or future RAG
implementation is authorized by this audit.
