# Phase 6 Internal Final Audit

**Status:** P6-16 = INTERNAL_AUDIT_COMPLETE; Phase 6 = INTERNAL_AUDIT_COMPLETE; External Review = PENDING; Phase 7 = NOT_STARTED.

## Baseline

- **Repository:** bluesblue320-hue/ielts-learning-agent
- **Branch:** `phase/6-hierarchical-learning-memory`
- **Base master SHA:** `3f1b4a5772b1a5fecf863d2711def11de6f5ff0f`
- **Implementation-start HEAD:** `9133487c9c1dd5287848f9ff09dccc34dc1ca9c7`
  (after the P6-01/P6-02 design commits `177faea`, `4ccc38a`, `9133487`)
- **Final HEAD:** `38dafd3fb27c56894f15b387dc3179b70cd08c91`

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

Re-run after all nodes completed:

| Gate | Result |
| --- | --- |
| `python -m pytest -q --strict-markers` (isolated PostgreSQL) | **870 passed, 1 warning** (Phase 5 baseline was 797; +73 Phase 6 tests) |
| `npm --prefix web run lint` | passed |
| `npm --prefix web run typecheck` | passed |
| `npm --prefix web test` | **10 passed** (Phase 5 baseline 8; +2 memory client tests) |
| `npm --prefix web run build` | passed (Next.js production build) |
| `npm --prefix web run test:e2e` | **2 passed** (Phase 5 closed loop + Phase 6 memory flow; Chromium, FastAPI, deterministic fakes, isolated PostgreSQL) |

CI: `.github/workflows/ci.yml` already enforces every gate above (pytest, lint, typecheck, web test, build, Playwright E2E with Chromium + PostgreSQL service) with no live DeepSeek credentials; no CI change was required.

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
```

## Files changed (grouped)

- Backend new modules: `app/memory/` (episode_queries, atoms, pattern_engine, progress_policy, profile, context, errors), `app/schemas/memory.py`, `app/api/routes/memory.py`.
- Backend touched: `app/main.py` (router), `app/api/errors.py` (+`episode_not_found`, memory persistence handlers), `app/schemas/errors.py` (+`EPISODE_NOT_FOUND`).
- Backend tests: `tests/test_memory_schemas.py`, `test_memory_queries.py`, `test_memory_atoms.py`, `test_progress_policy.py`, `test_memory_profile.py`, `test_memory_api.py`, `tests/e2e_server.py` (deterministic scripted payloads).
- Web: `web/src/lib/api/client.ts` (typed memory methods), `web/src/lib/memory-presentation.ts`, `web/src/app/history/**`, `web/src/app/progress/**`, `web/src/app/dashboard/page.tsx` (resume), `web/src/components/app-shell.tsx` (nav), `web/src/app/globals.css`, `web/src/lib/presentation.ts`, `web/e2e/phase6-memory.spec.ts`, `web/tests/api-client.test.ts`.
- Docs: `docs/PHASE6_GRAPH.md`, `docs/WRITING_MEMORY_POLICY.md`, `docs/PHASE6_AUDIT.md` (this file), `AGENTS.md`, `README.md`, `docs/ARCHITECTURE.md`.

## Known limitations

- **Unapplied initial-evaluation resume limitation (frozen):** an initial `WritingEvaluation` persisted by `/writing/evaluate` but never applied is NOT learner-owned; if browser/client state carrying its identity is lost before apply, `/writing/context` falls back to `initial_writing`. Phase 6 deliberately adds no ownership table to close this.
- Server-authoritative resume requires a known `learner_id` (no authentication/account discovery in scope).
- Trend/persistent-gap require 3 canonical observations; fewer yields `insufficient_history` (frozen v1 semantics).
- Local Windows note: this run required a dedicated isolated PostgreSQL instance; CI uses the existing PostgreSQL service container.

## Final status

```text
P6-01..P6-15 = COMPLETE
P6-16 = INTERNAL_AUDIT_COMPLETE
Phase 6 = INTERNAL_AUDIT_COMPLETE
External Review = PENDING
Phase 7 = NOT_STARTED
```

STOP — awaiting external review. Phase 7 must not start without separate explicit authority.
