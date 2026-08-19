# Phase 6 Internal Final Audit

**Status:** P6-16 = INTERNAL_AUDIT_COMPLETE; External Review = APPROVED; PR #10 = MERGED; Phase 6 = COMPLETE; Phase 7 = NOT_STARTED.

## Baseline

- **Repository:** bluesblue320-hue/ielts-learning-agent
- **Branch:** `phase/6-hierarchical-learning-memory`
- **Base master SHA:** `3f1b4a5772b1a5fecf863d2711def11de6f5ff0f`
- **Implementation-start HEAD:** `9133487c9c1dd5287848f9ff09dccc34dc1ca9c7`
  (after the P6-01/P6-02 design commits `177faea`, `4ccc38a`, `9133487`)
- **Reviewed HEAD (external review start):** `b5a83aa93efe7f24bd2612fbaa72f991d114f528`
- **PR head SHA (final branch state):** `0f0b5754a2a7430a04493343c0ee357b12e48f14`

## Merge finalization

Phase 6 was merged to `master` after external review approval:

| Item | Value |
| --- | --- |
| External Review | **APPROVED** |
| PR | **#10** — `feat: deliver Phase 6 hierarchical learning memory & longitudinal progress` |
| PR head SHA | `0f0b5754a2a7430a04493343c0ee357b12e48f14` |
| Merge commit | `b8e419d8c146c921539f4654b5aeb0b56ed6f425` |
| PR CI | **SUCCESS** (`Python 3.12 deterministic tests` passed before merge) |
| Master push CI | **SUCCESS** — run `32213726859`, workflow `CI`, event `push`, branch `master`, head SHA `b8e419d8c146c921539f4654b5aeb0b56ed6f425`, conclusion `success` |
| Final status | P6-01..P6-15 COMPLETE; P6-16 INTERNAL_AUDIT_COMPLETE; Phase 6 COMPLETE; Phase 7 NOT_STARTED |

The master push CI run (`32213726859`) executed the normal deterministic gates
in a single job (`Python 3.12 deterministic tests`): backend tests (pytest),
web quality gates (lint, typecheck, unit tests, production build), and Chromium
Playwright browser E2E — all passed. `.github/workflows/ci.yml` enforces these
gates on `pull_request`; the PR CI for #10 passed before merge.

## External review repair (targeted, no redesign)

The external review requested four targeted repairs. All were applied without
changing the frozen architecture, the planner, the persistence layer, or the
memory contract semantics beyond the explicit amendments below:

1. **Recent-practice skill attribution (fixed).** `LearningEpisodeSummary`
   now carries `practice_target_skill`, derived from the linked
   `WritingPractice.target_skill` (`null` for `initial_writing`).
   `recent_practice_count_for_skill()` counts targeted-practice episodes whose
   `practice_target_skill == requested skill`; the next-recommendation target
   (`recommendation_target_skill`) is retained and never used for practice
   attribution. Regression test: `test_review_regression_practice_target_differs_from_next_recommendation`
   (engine) and `test_review_regression_practice_attribution_at_api` (API),
   proving a practice completed for `task_response` with a next recommendation
   for `coherence_and_cohesion` is counted only for `task_response`.
2. **Late-arrival provenance (fixed).** `SkillObservationPoint` now carries
   `learning_update_id` (the persisted episode OWNING each evidence row).
   `SkillProgress.source_episode_ids` is derived from the SAME canonical trend
   window as `source_observation_ids` (exact L0 drill-down, independent of
   apply chronology); the new separate
   `recent_practice_source_episode_ids` field carries the
   `RECENT_PRACTICE_EPISODE_WINDOW` episode ids for practice provenance. No
   field is overloaded. Regression tests:
   `test_review_regression_late_arrival_provenance_matches_canonical_window`
   (engine) and `test_review_regression_late_arrival_provenance` (profile,
   isolated PostgreSQL) prove that with an older attempt applied later the
   trend is computed over canonical order and both provenance id lists point
   to the exact owning episodes.
3. **Raw database ids removed from normal progress UI (fixed).** The progress
   drill-down now renders ordinal, Chinese-first labels
   (`查看来源记录 1/2/3`) via `progressSourceLinkLabel()`; raw episode ids
   remain only in hrefs/React keys/API data. Frontend regression test added in
   `web/tests/presentation.test.ts` (asserts ordinal labels and the absence of
   the raw-id copy pattern in the page source).
4. **Unfinished-practice history contract (resolved by freezing a truthful v1
   limitation).** `/writing/history` returns applied L0 episodes only. Durable
   unfinished practices (`generated`, `submission_in_progress`,
   `submitted`-but-unapplied) are NOT surfaced in history once they stop being
   the relevant current practice; they remain exposed only through
   `/writing/context` while they are the practice linked to the current
   recommendation. No `pending_practices` collection and no new persistence
   were introduced. Frozen in `docs/WRITING_MEMORY_POLICY.md` §1.17
   ("Unfinished-practice history limitation") and the Phase 6 graph; regression
   test `test_review_unfinished_practice_history_v1_limitation` proves the
   history response shape (learner_id + episodes only) with a generated
   practice present in the database.

## Completed nodes

| Node | Status |
| --- | --- |
| P6-01 Baseline & Hierarchical Memory Capability Audit | COMPLETE (design) |
| P6-02 Hierarchical Learning Memory Contract Freeze | COMPLETE (design) |
| P6-03 Memory Domain Schemas + Provenance Contracts | COMPLETE |
| P6-04 L0 Episode Query Layer | COMPLETE |
| P6-05 L1 Atom Derivation | COMPLETE |
| P6-06 L2 Longitudinal Pattern Engine | COMPLETE |
| P6-07 L3 Learner Profile Read Model | COMPLETE |
| P6-08 History / Progress / Context APIs | COMPLETE |
| P6-09 Typed Web API Integration | COMPLETE |
| P6-10 Writing History UX | COMPLETE |
| P6-11 Longitudinal Progress UX | COMPLETE |
| P6-12 Resume Learning Context | COMPLETE |
| P6-13 Progressive Disclosure / Provenance UX | COMPLETE |
| P6-14 Resilience / Chinese Presentation / Accessibility | COMPLETE |
| P6-15 Full Validation / E2E / CI | COMPLETE |
| P6-16 Internal Final Audit | INTERNAL_AUDIT_COMPLETE |

## Invariant verification

| Invariant | Verified by |
| --- | --- |
| L0 = existing normalized persistence (no duplicate table) | P6-04 query layer reads existing rows only; no new model |
| L1/L2/L3 = read models (no `learning_memory` / `memory_atoms` / `memory_patterns` / `learner_profiles` tables) | P6-03/04/05/06/07 code review; no new table in `app/models/`; no migration |
| No Alembic migration | `git diff --stat` contains zero `migrations/` changes |
| No synthetic memory ids (`memory_atom_id` / `pattern_id` / `profile_id`) | P6-03 schema tests reject extra fields; schemas expose only persisted source ids |
| Provenance preserved (L3 → L2 → L1 → L0 → rows) | `SkillProgress.source_observation_ids` / `source_episode_ids`; episode detail full reconstruction; atoms carry authoritative ids |
| Progress deterministic | `tests/test_progress_policy.py` determinism tests; engine is pure |
| Trend threshold = 0.5 (`TREND_DELTA_THRESHOLD`) | `app/memory/progress_policy.py`; normative examples in `tests/test_progress_policy.py` |
| Trend window = 3 (`TREND_WINDOW`) | same |
| Practice episode window separately = 3 (`RECENT_PRACTICE_EPISODE_WINDOW`) | same; independent constant, never aliased to `TREND_WINDOW` |
| Current vs historical target separated | `target_snapshot` sourced only from `PracticeRecommendation.learner_target_band`; L3/persistent-gap use `Learner.writing_target_band` |
| Resume limitation truthful | `test_memory_api.py::test_unapplied_initial_evaluation_is_not_server_recoverable`; context falls back to `initial_writing`; no new ownership table |
| Older unfinished practice cannot override latest recommendation | `test_memory_api.py::test_older_unfinished_practice_does_not_override` |
| Current planner unchanged (`writing-practice-gap-v1`) | no change to `app/learner/planner.py`, `planning_policy.py`, or `app/schemas/planning.py` |
| `LearnerSkillState` remains state authority | L3 reads it via `_current_state`; no recomputation of EWMA in memory layer |
| No provider calls for memory reads | `test_memory_api.py::test_reads_make_zero_provider_calls`; read routes have no provider dependency |
| No vector DB / no RAG / no LangGraph / no multi-agent / no TencentDB runtime dependency | dependencies unchanged (`pyproject.toml` untouched); no provider abstraction introduced |
| Phase 7 not started | no Phase 7 files; AGENTS.md status |

## Public APIs (frozen read contracts)

- `GET /learners/{learner_id}/writing/history` — L0 episode list (created_at DESC, id DESC)
- `GET /learners/{learner_id}/writing/history/{episode_id}` — full L0 reconstruction
- `GET /learners/{learner_id}/writing/progress` — L2 patterns + L3 profile section
- `GET /learners/{learner_id}/writing/context` — server-authoritative resume context

No fifth `/profile` endpoint was added.

## Architecture implementation

- **L0:** `app/memory/episode_queries.py` — read-only list/detail over `LearningUpdate` joined to evaluation/attempt/recommendation/practice; `occurred_at = LearningUpdate.created_at`; episode-type derivation via the 1:1 practice→attempt→evaluation→update link.
- **L1:** `app/memory/atoms.py` — `skill_observation` (evidence projection), `practice_completed` (submitted + applied, `completed_at = LearningUpdate.created_at`), `target_snapshot` (recommendation band only), `recommendation_observation` (full decision).
- **L2:** `app/memory/progress_policy.py` + `app/memory/pattern_engine.py` — frozen constants and pure trend / persistent-gap / count functions over canonical observation sequences.
- **L3:** `app/memory/profile.py` — `WritingProgressResponse` assembly; current state read (not recomputed) from `LearnerSkillState`.
- **Context/resume:** `app/memory/context.py` — single latest-`LearningUpdate` lookup → recommendation → linked practice → non-recursive resume action.
- **Provenance:** every read model exposes `learning_update_id` / `learning_evidence_id` / `writing_evaluation_id` / `writing_practice_id` / `recommendation_id` / `attempt_id`.
- **Progressive disclosure:** web UX shows summaries first; episode detail is opened explicitly; raw source ids appear only in the collapsed audit block.

## Frontend

- `/history` — episode list (type, time, four skill bands, recommendation) + drill-down to episode detail (question, essay, criteria, feedback, strengths/weaknesses/error_tags/recommended_skills, practice, recommendation, audit provenance).
- `/progress` — per-skill L3/L2 cards: current estimate, target, trend badge, persistent gap, evidence/recent counts, drill-down links to source episodes.
- Dashboard resume — server-authoritative `resume_action` rendering (initial_writing / no_action / generate_practice / submit_practice / await_submission / complete_practice); explicit user click to continue; no automatic generation.
- Chinese-first copy; loading/empty/error/retry states; semantic HTML, `aria-live`, `role="alert"`, focus-visible, responsive CSS; no charting library; persisted English content rendered as-is.

## Persistence

- New tables: NONE
- Migrations: NONE
- `app/models/` unchanged

## Planner

`writing-practice-gap-v1` unchanged. No memory-aware planner inputs, reason codes, or qualitative-memory inputs were introduced.

## External memory

- TencentDB Agent Memory runtime dependency: NONE
- Memory adapter: documentation-only (no runtime abstraction introduced)

## Vector / RAG

- Vector database: NONE (no pgvector / Milvus / Qdrant / Elasticsearch / BM25)
- RAG / embeddings / LangGraph / multi-agent: NONE

## Fresh validation results

Re-run from the final repaired HEAD (all local/full deterministic gates):

| Gate | Result |
| --- | --- |
| `python -m pytest -q --strict-markers` (isolated PostgreSQL) | **876 passed, 1 warning** (Phase 5 baseline 797; +79 Phase 6 tests incl. review regressions) |
| `npm --prefix web run lint` | passed |
| `npm --prefix web run typecheck` | passed |
| `npm --prefix web test` | **11 passed** (Phase 5 baseline 8; +3 memory/presentation tests) |
| `npm --prefix web run build` | passed (Next.js production build) |
| `npm --prefix web run test:e2e` | **2 passed** (Phase 5 closed loop + Phase 6 memory flow; Chromium, FastAPI, deterministic fakes, isolated PostgreSQL) |

CI truth: the local/full deterministic gates above were run from the final
repaired HEAD and all passed (876 backend, 11 frontend unit, 2 Playwright).
GitHub CI evidence is separate and recorded in [Merge finalization](#merge-finalization):
PR #10 CI = SUCCESS and the master push CI run for the merge commit
`b8e419d` (run `32213726859`) = SUCCESS, executing the same gates.

## Commits (Phase 6, chronological)

```text
177faea docs: audit Phase 6 hierarchical memory baseline
4ccc38a docs: freeze Phase 6 hierarchical memory contract
9133487 docs: refine Phase 6 memory contract
016b876 feat: define Phase 6 memory schemas
46867ae feat: add Phase 6 episode queries
35d6b12 feat: derive Phase 6 learning atoms
9b88195 feat: add deterministic writing progress engine
ae77c08 feat: assemble learner memory profile
5b93e83 feat: expose Phase 6 learning memory APIs
eddc9b7 feat: add typed Phase 6 web memory client
4c2aa62 feat: add writing history experience
336ba93 feat: add writing progress experience
210dc9f feat: add server-authoritative learning resume
882deff feat: add memory drill-down experience
d38af52 fix: harden Phase 6 memory experience
38dafd3 test: validate Phase 6 learning memory flow
8eb7fc2 docs: complete Phase 6 internal audit
95c2591 test: scope memory test overrides to owned keys
b5a83aa chore: ignore playwright test artifacts
fb078ea fix: repair practice attribution and trend provenance
d16e460 fix: hide raw database ids in progress UI
d4f8534 docs: freeze unfinished-practice history v1 limitation
4268eb8 docs: update Phase 6 audit for external review repairs
fd0ab25 docs: sync final audit HEAD
```

## Files changed (grouped)

- Backend new modules: `app/memory/` (episode_queries, atoms, pattern_engine, progress_policy, profile, context, errors), `app/schemas/memory.py`, `app/api/routes/memory.py`.
- Backend touched: `app/main.py` (router), `app/api/errors.py` (+`episode_not_found`, memory persistence handlers), `app/schemas/errors.py` (+`EPISODE_NOT_FOUND`).
- Backend tests: `tests/test_memory_schemas.py`, `test_memory_queries.py`, `test_memory_atoms.py`, `test_progress_policy.py`, `test_memory_profile.py`, `test_memory_api.py`, `tests/e2e_server.py` (deterministic scripted payloads).
- Web: `web/src/lib/api/client.ts` (typed memory methods), `web/src/lib/memory-presentation.ts`, `web/src/app/history/**`, `web/src/app/progress/**`, `web/src/app/dashboard/page.tsx` (resume), `web/src/components/app-shell.tsx` (nav), `web/src/app/globals.css`, `web/src/lib/presentation.ts`, `web/e2e/phase6-memory.spec.ts`, `web/tests/api-client.test.ts`.
- Docs: `docs/PHASE6_GRAPH.md`, `docs/WRITING_MEMORY_POLICY.md`, `docs/PHASE6_AUDIT.md` (this file), `AGENTS.md`, `README.md`, `docs/ARCHITECTURE.md`.

## Known limitations

- **Unapplied initial-evaluation resume limitation (frozen):** an initial `WritingEvaluation` persisted by `/writing/evaluate` but never applied is NOT learner-owned; if browser/client state carrying its identity is lost before apply, `/writing/context` falls back to `initial_writing`. Phase 6 deliberately adds no ownership table to close this.
- **Unfinished-practice history limitation (frozen):** `/writing/history` returns applied L0 episodes only; durable unfinished practices (`generated`, `submission_in_progress`, `submitted`-but-unapplied) are not surfaced in history once they stop being the relevant current practice. They remain exposed through `/writing/context` only while they are the practice linked to the current recommendation. No `pending_practices` collection exists in v1.
- Server-authoritative resume requires a known `learner_id` (no authentication/account discovery in scope).
- Trend/persistent-gap require 3 canonical observations; fewer yields `insufficient_history` (frozen v1 semantics).
- Local Windows note: this run required a dedicated isolated PostgreSQL instance; CI uses the existing PostgreSQL service container.

## Final status

```text
P6-01..P6-15 = COMPLETE
P6-16 = INTERNAL_AUDIT_COMPLETE
External Review = APPROVED
PR #10 = MERGED
Phase 6 = COMPLETE
Phase 7 = NOT_STARTED
```

STOP — Phase 7 must not start without separate explicit authority.
