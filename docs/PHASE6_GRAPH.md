# Phase 6 Graph — Hierarchical Learning Memory & Longitudinal Progress

## Document status

**EXECUTED — P6-01 through P6-15 COMPLETE; P6-16 = INTERNAL_AUDIT_COMPLETE; Phase 6 = INTERNAL_AUDIT_COMPLETE; External Review = PENDING; Phase 7 = NOT_STARTED.**

The design run (P6-01/P6-02) completed and passed external design review
repair. The implementation run then executed P6-03 through P6-16 continuously
on this branch; see [PHASE6_AUDIT.md](PHASE6_AUDIT.md) for the final internal
audit, fresh validation results, and the commit list. External review approval
is not claimed.

This graph is frozen on `phase/6-hierarchical-learning-memory`, created from
`master` at `3f1b4a5772b1a5fecf863d2711def11de6f5ff0f` (`docs: finalize Phase 5
merged status`). The working tree was clean before the branch was created.

This run is authorized for DESIGN/BASELINE work only:

- `P6-01` — Baseline & Hierarchical Memory Capability Audit
- `P6-02` — Hierarchical Learning Memory Contract Freeze

No application code, no frontend code, no Alembic migration, and no test
changes were made in this run. Phase 6 implementation (`P6-03` or later) is
NOT authorized and has NOT started. Phase 7 is NOT started.

The authoritative frozen contract produced by this run is
[docs/WRITING_MEMORY_POLICY.md](WRITING_MEMORY_POLICY.md).

---

## 1. Goal and architecture

Phase 6 transforms the existing durable Writing history into an explicit
Learning Memory subsystem. After Phase 6 the product must be able to answer:

- What Writing work has this learner completed?
- What happened in each learning episode?
- What atomic facts were learned from those episodes?
- What longitudinal patterns are emerging?
- What is the learner's current long-term Writing profile?
- Which canonical Writing skills are improving, stable, declining, or
  persistently below target?
- What targeted practices have been completed?
- Where is the learner currently located in the Writing learning loop?
- How should the UI resume the current server-authoritative context?

Phase 6 is structured learning memory, not a generic chatbot-memory feature.

### 1.1 Memory hierarchy

The memory model adapts a hierarchical memory architecture to IELTS learning:

```text
L3 — Learner Learning Profile
  -> L2 — Learning Pattern
      -> L1 — Learning Atom
          -> L0 — Learning Episode
              -> authoritative persisted PostgreSQL rows
```

| Level | Name | Question it answers |
| --- | --- | --- |
| L0 | Learning Episode | What happened, and what is the authoritative source? |
| L1 | Learning Atom | What small structured facts were learned? |
| L2 | Learning Pattern | What longitudinal patterns are emerging? |
| L3 | Learner Profile | What does the system know long-term? |

### 1.2 Progressive disclosure

```text
L3 profile
  -> L2 patterns if detail required
  -> L1 atoms if evidence required
  -> L0 episodes if source verification required
```

The system MUST NOT send every historical essay/evaluation into an LLM or
future Agent context by default. High-level memory must remain drillable back
to authoritative evidence.

### 1.3 Frozen ownership

- **PostgreSQL:** source of truth. L0 stays in existing normalized rows.
- **FastAPI:** read-model derivation, deterministic pattern engine, public
  read contracts.
- **Next.js:** presentation only.
- **No external memory vendor** (no TencentDB runtime dependency).
- **No vector database, no RAG, no embedding models** in Phase 6.
- **No LLM-authored longitudinal facts.** Trend and persistent-gap facts are
  deterministic.

---

## 2. Dependency graph

```text
START
  ↓
P6-01 Baseline & Hierarchical Memory Capability Audit [COMPLETE]
  ↓
P6-02 Hierarchical Learning Memory Contract Freeze [COMPLETE]
  ↓
P6-03 Memory Domain Schemas + Provenance Contracts [COMPLETE]
  ↓
P6-04 L0 Episode Query Layer [COMPLETE]
  ↓
P6-05 L1 Atom Derivation (read model) [COMPLETE]
  ↓
P6-06 L2 Longitudinal Pattern Engine [COMPLETE]
  ↓
P6-07 L3 Learner Profile Read Model [COMPLETE]
  ↓
P6-08 History / Progress / Context APIs [COMPLETE]
  ↓
P6-09 Typed Web API Integration [COMPLETE]
  ↓
P6-10 Writing History UX [COMPLETE]
  ↓
P6-11 Longitudinal Progress UX [COMPLETE]
  ↓
P6-12 Resume Learning Context [COMPLETE]
  ↓
P6-13 Progressive Disclosure / Provenance UX [COMPLETE]
  ↓
P6-14 Resilience / Chinese Presentation / Accessibility [COMPLETE]
  ↓
P6-15 Backend + Frontend + Browser E2E / CI [COMPLETE]
  ↓
P6-16 Internal Final Audit [INTERNAL_AUDIT_COMPLETE]
  ↓
STOP
  ↓
External Review [PENDING]
```

Dependency rule: a node may be activated only when every declared dependency is
`COMPLETE`. `P6-03` through `P6-16` remain `NOT_STARTED` until the frozen
contract (`WRITING_MEMORY_POLICY.md`) is accepted and Phase 6 implementation is
explicitly authorized.

---

## 3. P6-01 — Baseline & Hierarchical Memory Capability Audit — COMPLETE

**Authority:** read-only audit of `master` at `3f1b4a5772b1a5fecf863d2711def11de6f5ff0f`
(working tree clean). **Deliverable:** the ten explicit audit answers below,
the trend-series decision, the API-shape decision, and the
read-model/materialization decision. These findings are normative for the
contract frozen in P6-02.

### 3.1 Audit scope

Inspected persistence models (`app/models/learning.py`, `app/models/writing.py`,
`app/models/practice.py`), the learner domain (`app/learner/state_engine.py`,
`planner.py`, `writing_evidence.py`), services
(`app/services/learning_application.py`, `practice_completion.py`,
`practice_submission.py`, `practice_generation.py`), schemas
(`app/schemas/learning_api.py`, `planning.py`, `writing.py`, `practice.py`,
`learner.py`), current learner/writing/practice API routes, the Phase 5 web
client (`web/src/lib/api/client.ts`, `learner-context.tsx`,
`dashboard/page.tsx`), the existing tests, and the browser E2E. No change was
made to any implementation.

### 3.2 Audit answers

**1. Can `LearningUpdate` safely serve as the learner-owned L0 episode
anchor? — YES.**

`LearningUpdate` is the only row that proves a persisted evaluation has been
accepted into a specific learner's state. It is learner-scoped (`learner_id`
FK `RESTRICT`), created only inside the atomic Phase 3 apply transaction
(`1 LearningUpdate + 4 LearningEvidence + 4 LearnerSkillState +
1 PracticeRecommendation`), carries the frozen policy versions
(`skill_taxonomy_version`, `state_policy_version`, `planner_version`), and has
`created_at`. Its `writing_evaluation_id` is globally unique
(`uq_learning_update_writing_evaluation_id`), so one evaluation can never be
owned by two learners. A raw `WritingAttempt` alone has no learner reference
and MUST NOT be treated as learner-owned memory.

**2. Can `initial_writing` vs `targeted_practice` be derived
deterministically? — YES.**

The chain `WritingPractice.attempt_id -> WritingAttempt -> WritingEvaluation
-> LearningUpdate.writing_evaluation_id` is 1:1 at every hop
(`writing_practices.attempt_id` UNIQUE, `writing_evaluations.attempt_id`
UNIQUE, `learning_updates.writing_evaluation_id` UNIQUE). Therefore, for one
episode:

- `targeted_practice` ⇔ exactly one `WritingPractice` references the episode's
  evaluation attempt;
- `initial_writing` ⇔ no `WritingPractice` references that attempt.

No ambiguity is possible. A submitted-but-not-completed practice has an attempt
and evaluation but no `LearningUpdate` yet, so it is not yet an episode; it is
a pending practice in practice history and a resume point in context.

**3. Can historical per-skill observations be reconstructed? — YES, exactly.**

`LearningEvidence` is immutable and append-only: one row per canonical skill
per applied update, storing `observed_band` (IELTS half-band),
`source_created_at` + `source_attempt_id` (the immutable canonical-order
values), full provenance, and a composite ownership FK back to
`LearningUpdate`. The canonical index
(`learner_id`, `skill`, `source_created_at`, `source_attempt_id`) makes the
per-skill observation series directly queryable in deterministic order.

**4. Can post-update learner-state history be reconstructed exactly? — YES,
via deterministic replay (with a documented nuance).**

`LearnerSkillState` stores only the CURRENT materialized row (updated in
place; `revision` increments); historical materialized rows are not persisted.
However, because all evidence is persisted and the `writing-state-ewma-v1`
replay is exact and deterministic (full canonical replay from the complete
accepted set), the state trajectory after each canonical observation is exactly
reconstructible by replaying the evidence prefix. Nuance: "state after update
N" is not well-defined by `LearningUpdate` order, because late-arriving older
evidence can be applied by a later update; canonical reconstruction is per
skill over the canonical evidence sequence. The memory layer (P6-02 trend
policy) deliberately uses observed bands rather than replay, so this nuance
does not block the memory contract.

**5. Can recommendation history be reconstructed? — YES.**

`PracticeRecommendation` is persisted 1:1 per `LearningUpdate`
(`learning_update_id` UNIQUE) and stores the complete frozen decision:
`decision_type`, `target_skill`, `learner_target_band`, `current_estimate`,
`reason_codes` (JSONB, exact allowed sequences), `planner_version`, and the
full `state_snapshot` (JSONB), plus `created_at`. Every historical decision is
directly readable.

**6. Can practice history be reconstructed? — YES.**

`WritingPractice` rows are durable and learner-scoped, with `recommendation_id`
(UNIQUE, composite FK ownership), `target_skill`, `lifecycle_state`
(`generated` / `submission_in_progress` / `submitted`), `attempt_id` (UNIQUE,
nullable), `created_at`, and `updated_at`. The linkage
`practice -> attempt -> evaluation -> learning update` is reconstructible via
`attempt_id` → `WritingAttempt` → `WritingEvaluation.attempt_id` (UNIQUE) →
`LearningUpdate.writing_evaluation_id` (UNIQUE). "Completed practice" in memory
semantics = `submitted` AND its evaluation has been applied (a `LearningUpdate`
exists). Generated-but-unsubmitted practices are durable history but are never
called "completed".

**7. Can provenance from high-level memory to raw evidence be maintained? —
YES.**

Stable persisted ids exist at every hop: L3 profile → per-skill summary
carries evidence/episode ids; L2 pattern → source `LearningEvidence.id` /
`LearningUpdate.id`; L1 atom → exact row ids (`LearningEvidence.id`,
`WritingPractice.id`, `PracticeRecommendation.id`, `LearningUpdate.id`); L0
episode → `LearningUpdate.id` → `writing_evaluation_id` →
`WritingEvaluation.id` → `attempt_id` → `WritingAttempt` (question, essay,
word count, created_at). Every FK in the chain is `RESTRICT`, so applied
history cannot silently disappear.

**8. Which L1/L2/L3 objects can be read models? — ALL of them.**

- **L1:** `skill_observation` IS the persisted `LearningEvidence` row;
  `practice_completed` is a projection over `WritingPractice` +
  `LearningUpdate`; `target_snapshot` is persisted on
  `PracticeRecommendation.learner_target_band` and
  `Learner.writing_target_band`; `recommendation_observation` IS the persisted
  `PracticeRecommendation` row.
- **L2:** trend, persistent gap, and counts are pure functions over persisted
  observation and practice rows.
- **L3:** the learner Writing profile is an aggregate read model over L2 plus a
  read of the current `LearnerSkillState` (read, not duplicated).

**9. Which, if any, should be materialized? — None for v1.**

Materialization would only be triggered by a proven requirement: (a) latency
targets at large history (not plausible at v1: four skills, half-band
observations, small counts); (b) LLM/Agent context needing stable opaque ids
(not needed: structured API responses already expose stable persisted row
ids); or (c) cross-cutting queries made slow by recomputation (not the case).
If materialization is later justified, it must preserve source references and
versioned policy and go through a future graph node with migration permission.

**10. Is any new database table actually required? — NO.**

L0 uses the existing normalized rows unchanged. L1 atoms already exist as
persisted rows. L2/L3 are recomputed read models. The existing unique
constraints and composite FKs already enforce the provenance invariants that a
dedicated memory table would need to re-encode. No migration is proposed in
this run; no migration is required for the v1 contract.

### 3.3 Trend-series decision (frozen)

**Choice: criterion observed bands are the canonical trend series.**

The alternative (post-update EWMA estimates) is documented and rejected for
v1:

| Consideration | Criterion observed bands (chosen) | Post-update EWMA estimates |
| --- | --- | --- |
| Persistence | Directly persisted, immutable | Not persisted; must be replayed |
| Dependency on replay engine / policy version | None | Full replay dependency; a future state-policy change would silently reinterpret history |
| Independence from state engine | Memory trend independent of `LearnerSkillState` | Trend would be a double-derived fact (derived from derived state) |
| Drill-down | L2 trend → 3 L1 `skill_observation` atoms → evidence rows | Requires replay trace, not raw atoms |
| Noise | Raw half-band observations can be noisy | Smoothed |

The frozen policy (`writing-progress-v1`) defines trend over the canonical
per-skill observation sequence (ordered by `source_created_at`,
`source_attempt_id`), using exact `Decimal` arithmetic, and does not mix in
EWMA estimates.

### 3.4 Practice-history decision (frozen)

Only durable `WritingPractice` rows count as practices. `generated`,
`submission_in_progress`, and `submitted` are all durable practice states;
`submitted` + applied (a `LearningUpdate` exists) is the only "completed"
state in memory semantics. Generated-but-unsubmitted practice is never called
"completed".

### 3.5 API-shape decision (frozen)

Four read endpoints, no separate profile endpoint:

```text
GET /learners/{learner_id}/writing/history
GET /learners/{learner_id}/writing/history/{episode_id}
GET /learners/{learner_id}/writing/progress
GET /learners/{learner_id}/writing/context
```

`/progress` carries the L3 profile section (target band + current four-skill
state + per-skill summary) beside the L2 per-skill patterns, avoiding a fifth
`/profile` endpoint while keeping L3 semantics explicit. `/context` is
justified because no existing endpoint can answer "where should the learner
continue" server-authoritatively (there is no latest-recommendation or
latest-practice read today). The context contract is frozen in
`WRITING_MEMORY_POLICY.md` §1.17: current recommendation = the
`PracticeRecommendation` owned by the latest `LearningUpdate`
(`created_at DESC`, `id DESC`); relevant practice = ONLY the practice linked to
that current recommendation (older unfinished practices never override it);
episode `occurred_at` = `LearningUpdate.created_at` (single source); and the
resume v1 limitation is frozen — an unapplied initial `WritingEvaluation` is
not learner-owned and cannot be recovered from `learner_id` alone, so context
falls back to `initial_writing` when browser state is lost before apply, and
Phase 6 will NOT add a new ownership table to close this limitation.

---

## 4. P6-02 — Hierarchical Learning Memory Contract Freeze — COMPLETE

**Deliverable:** [docs/WRITING_MEMORY_POLICY.md](WRITING_MEMORY_POLICY.md),
the normative memory policy for Phase 6.

Frozen version identifiers:

```text
writing-memory-v1
writing-progress-v1
```

The policy freezes: memory hierarchy (L0–L3), semantics and ownership of each
level, provenance contract, progressive disclosure rule, history ordering,
trend semantics, persistent-gap semantics, practice-history semantics, the
state-vs-memory boundary, the planner boundary, the qualitative-data boundary,
the read-model/materialization decision, the API contract candidates, and the
memory-adapter decision. No database schema is frozen (the audit proves no
table is required for v1).

**External design review repair (docs-only).** After the first design
submission, targeted contract repair was applied to `WRITING_MEMORY_POLICY.md`
and this graph without changing the approved overall architecture: the resume
v1 limitation is frozen; the current-recommendation / relevant-practice rule
for `/writing/context` is frozen with a non-recursive transition;
`target_snapshot` provenance is restricted to
`PracticeRecommendation.learner_target_band` (no current-target fallback);
`writing-progress-v1` uses `TREND_DELTA_THRESHOLD = Decimal("0.5")`
(half-band granularity); practice recency uses the separate
`RECENT_PRACTICE_EPISODE_WINDOW = 3`; the completion timestamp is frozen to
`LearningUpdate.created_at`; and synthetic memory ids (`memory_atom_id`,
`pattern_id`, `profile_id`) are forbidden. Phase 6 remains
`DESIGN_REVIEW_PENDING` — external review approval is not claimed yet.

Statuses after this design run:

```text
Phase 1 = COMPLETE
Phase 2 = COMPLETE
Phase 3 = COMPLETE
Phase 4 = COMPLETE
Phase 5 = COMPLETE
Phase 6 = DESIGN_REVIEW_PENDING (design run) -> INTERNAL_AUDIT_COMPLETE (after P6-16)
P6-01 = COMPLETE
P6-02 = COMPLETE
P6-03..P6-15 = COMPLETE (implementation run)
P6-16 = INTERNAL_AUDIT_COMPLETE
External Review = PENDING
Phase 7 = NOT_STARTED
```

---

## 5. Node definitions (P6-03 .. P6-16 — COMPLETE / INTERNAL_AUDIT_COMPLETE)

Each node below was executed in dependency order during the authorized
continuous implementation run. Node wording reflects the P6-01 audit:
L1/L2/L3 are read models over existing PostgreSQL rows; no new table; no
external memory vendor; no vector database. The execution record, acceptance
evidence, and fresh validation results are in [PHASE6_AUDIT.md](PHASE6_AUDIT.md).

### P6-03 — Memory Domain Schemas + Provenance Contracts

- **Purpose:** Freeze Pydantic v2 read-model schemas for L0 episode summaries
  and detail, L1 atoms, L2 patterns, L3 profile, and resume context, with
  stable provenance fields (ids) on every object.
- **Scope:** New `app/schemas/memory.py` (or `app/schemas/memory/` package if
  justified by size) with strict schemas (`extra="forbid"`), IELTS band
  validation reuse, and provenance field requirements per
  `WRITING_MEMORY_POLICY.md`.
- **Allowed files:** `app/schemas/memory*`, the contract doc, tests for the
  schemas.
- **Forbidden scope:** ORM models, services, routes, frontend, migrations,
  LLM/provider calls, planner changes.
- **Dependencies:** `P6-02` (contract), existing `app/schemas/*`.
- **Acceptance criteria:** Every schema validates provenance ids; L3/L2/L1/L0
  shapes match the policy doc exactly; no schema duplicates `LearnerSkillState`
  semantics as authoritative state; no invented persistent memory ids
  (`memory_atom_id`, `pattern_id`, `profile_id`) — only the existing
  authoritative source ids (`learning_update_id`, `learning_evidence_id`,
  `writing_evaluation_id`, `writing_practice_id`, `recommendation_id`,
  `attempt_id`); derived L2 objects are identified structurally by
  `learner + skill + pattern kind + policy version`.
- **Required tests:** schema validation unit tests covering valid and invalid
  shapes, provenance-id presence, band validation, extra-field rejection.
- **Migration permission:** NONE.
- **Route-back conditions:** Any contract mismatch with
  `WRITING_MEMORY_POLICY.md` routes back to `P6-02` for a contract decision
  before code is accepted.
- **Stop conditions:** All schemas validated and committed; no runtime code
  beyond schemas.

### P6-04 — L0 Episode Query Layer

- **Purpose:** Read-only service that lists learner-owned L0 episodes in
  deterministic order (`LearningUpdate.created_at DESC`, `LearningUpdate.id
  DESC`) and reconstructs one full episode (update, evaluation, attempt,
  evidence set, recommendation, linked practice) with provenance.
- **Scope:** New read service in `app/memory/` (e.g., `episode_queries.py`)
  using existing models; derive `initial_writing` vs `targeted_practice` via
  the 1:1 practice→attempt→evaluation→update link.
- **Allowed files:** `app/memory/`, `app/schemas/memory*`, tests.
- **Forbidden scope:** New tables, mutations, evaluation/state/planner policy
  changes, LLM calls, web code.
- **Dependencies:** `P6-02`, `P6-03`.
- **Acceptance criteria:** History ordering deterministic and documented;
  episode-type derivation exact; full episode reconstruction includes the
  complete provenance chain; no duplicate of L0 data.
- **Required tests:** ordering tests (ties broken by id), episode-type
  derivation (initial vs practice), reconstruction round-trip against
  isolated PostgreSQL, ownership checks.
- **Migration permission:** NONE.
- **Route-back conditions:** If a persisted row cannot satisfy an L0 query,
  route back to `P6-01` (audit) to re-examine the anchor before any schema
  change.
- **Stop conditions:** Query layer validated and committed.

### P6-05 — L1 Atom Derivation (read model)

- **Purpose:** Expose L1 atoms as read models: `skill_observation` (projection
  of `LearningEvidence`), `practice_completed` (projection over
  `WritingPractice` + `LearningUpdate`), `target_snapshot` (from
  `PracticeRecommendation.learner_target_band` / `Learner.writing_target_band`),
  `recommendation_observation` (projection of `PracticeRecommendation`).
- **Scope:** Derivation functions in `app/memory/` mapping persisted rows to
  L1 atoms with provenance; no new rows.
- **Allowed files:** `app/memory/`, `app/schemas/memory*`, tests.
- **Forbidden scope:** New tables, mutations, LLM, web code, planner changes.
- **Dependencies:** `P6-02`, `P6-03`, `P6-04`.
- **Acceptance criteria:** Every atom carries provenance back to its
  authoritative L0 source; no provenance-free atom can be produced;
  `practice_completed` requires `submitted` + applied evaluation.
- **Required tests:** atom derivation for all four kinds, provenance presence,
  practice-completed gating, isolation from non-applied practices.
- **Migration permission:** NONE.
- **Route-back conditions:** If an atom cannot be derived without new data,
  route back to `P6-01`/`P6-02` before proposing persistence.
- **Stop conditions:** Derivation validated and committed.

### P6-06 — L2 Longitudinal Pattern Engine

- **Purpose:** Deterministic engine computing per-skill L2 patterns: trend
  (`improving` / `stable` / `declining` / `insufficient_history`), persistent
  gap, observation counts, and completed-practice counts, exactly per
  `writing-progress-v1` in `WRITING_MEMORY_POLICY.md`.
- **Scope:** Frozen constants module (e.g., `app/memory/progress_policy.py`
  mirroring `TREND_WINDOW = 3`, `TREND_DELTA_THRESHOLD = Decimal("0.5")`, and
  the separately versioned `RECENT_PRACTICE_EPISODE_WINDOW = 3`) and pure
  engine (`app/memory/pattern_engine.py`) over canonical observation
  sequences.
- **Allowed files:** `app/memory/`, `app/schemas/memory*`, tests.
- **Forbidden scope:** LLM inference of longitudinal facts, hidden weighting,
  confidence scores, planner inputs, new tables, web code.
- **Dependencies:** `P6-02` (trend/persistent-gap policy), `P6-04`, `P6-05`.
- **Acceptance criteria:** Engine matches the policy examples exactly with
  exact `Decimal` arithmetic (`TREND_DELTA_THRESHOLD = 0.5`; trend
  insufficient when fewer than 3 observations); `recent_practice_count` uses
  the separate `RECENT_PRACTICE_EPISODE_WINDOW`, never `TREND_WINDOW`; every
  pattern exposes source observation ids and source episode ids for drill-down
  and has no invented pattern id; determinism tests with reordered input.
- **Required tests:** trend window/threshold tests (all branches:
  insufficient, improving, stable, declining), persistent-gap tests, count
  tests, drill-down id presence, determinism.
- **Migration permission:** NONE.
- **Route-back conditions:** Any mismatch with the frozen policy routes back
  to `P6-02`.
- **Stop conditions:** Engine validated and committed.

### P6-07 — L3 Learner Profile Read Model

- **Purpose:** Assemble the L3 learner Writing profile: target band, current
  four-skill state (read from `LearnerSkillState`), and per-skill longitudinal
  summary (current estimate, evidence count, trend, persistent gap, recent
  observation count, recent practice count, latest observation time, last
  episode id), all traceable to L2/L1/L0.
- **Scope:** Read-model assembly in `app/memory/`; reuse of `P6-06` outputs
  and current state reads.
- **Allowed files:** `app/memory/`, `app/schemas/memory*`, tests.
- **Forbidden scope:** Replacing `LearnerSkillState`, duplicating current-state
  computation, unsupported qualitative statements, new tables, web code.
- **Dependencies:** `P6-06`, `P6-04`.
- **Acceptance criteria:** Profile structure matches the policy; every field is
  traceable; current-state fields reference (not replace) `LearnerSkillState`;
  no qualitative statements such as "the learner is bad at grammar".
- **Required tests:** profile assembly, traceability ids, boundary states
  (UNOBSERVED learner), determinism.
- **Migration permission:** NONE.
- **Route-back conditions:** If a profile field cannot be traced, route back to
  `P6-02`.
- **Stop conditions:** Read model validated and committed.

### P6-08 — History / Progress / Context APIs

- **Purpose:** Add the four frozen read endpoints:
  `GET .../writing/history`, `GET .../writing/history/{episode_id}`,
  `GET .../writing/progress`, `GET .../writing/context`; thin routes delegating
  to the memory services; safe error envelope reuse.
- **Scope:** New routes in `app/api/routes/` (e.g., `memory.py`) wired into
  `app/main.py`; services from `P6-04`..`P6-07`; no policy changes.
- **Allowed files:** `app/api/routes/memory.py`, `app/main.py` wiring,
  `app/services` or `app/memory` read services, tests.
- **Forbidden scope:** Mutations, planner changes, practice lifecycle changes,
  authentication, new tables, web code, LLM calls.
- **Dependencies:** `P6-04`, `P6-05`, `P6-06`, `P6-07`.
- **Acceptance criteria:** All four endpoints return the frozen schemas;
  history order deterministic; episode detail enforces learner ownership and
  defines `occurred_at` exactly as `LearningUpdate.created_at`; context
  implements the frozen current-recommendation / relevant-practice rule
  (latest `LearningUpdate` by `created_at DESC`, `id DESC`; relevant practice
  is ONLY the practice linked to that recommendation; older unfinished
  practices never override) with the frozen non-recursive resume-action
  transition and NO automatic next-practice generation; the resume v1
  limitation is enforced (unapplied initial evaluations are not discoverable
  from `learner_id`); stable error codes
  (`learner_not_found`, `episode_not_found`, `persistence_unavailable`).
- **Required tests:** API tests for all endpoints against isolated PostgreSQL;
  ownership; ordering; error mapping; context resume-action branches.
- **Migration permission:** NONE.
- **Route-back conditions:** If an endpoint needs data not derivable from
  persisted rows, route back to `P6-01`/`P6-02`.
- **Stop conditions:** All endpoints validated and committed.

### P6-09 — Typed Web API Integration

- **Purpose:** Extend the typed client (`web/src/lib/api/client.ts`) with
  methods for history, episode detail, progress, and context; TypeScript types
  mirroring the frozen schemas.
- **Scope:** Client types and methods only; no business logic in the browser.
- **Allowed files:** `web/src/lib/api/client.ts`, `web/tests/api-client.test.ts`.
- **Forbidden scope:** Server actions, route handlers with business logic,
  state recomputation, new dependencies, backend changes.
- **Dependencies:** `P6-08`.
- **Acceptance criteria:** Typed methods match the frozen responses; unit tests
  with a fake fetch cover success and error envelopes.
- **Required tests:** `npm --prefix web run typecheck`, `npm --prefix web test`.
- **Migration permission:** NONE.
- **Route-back conditions:** API type mismatches route back to `P6-08`.
- **Stop conditions:** Client validated and committed.

### P6-10 — Writing History UX

- **Purpose:** `/history` page listing learner-owned episodes in Chinese
  (type, time, skill summary, recommendation) with drill-down to episode
  detail.
- **Scope:** New Next.js page and components under `web/src/app/history/`;
  presentation only.
- **Allowed files:** `web/src/app/history/**`, `web/src/components/**`,
  `web/src/lib/presentation.ts`.
- **Forbidden scope:** Backend changes, essay/evaluation persistence in
  browser storage, machine translation of persisted content, charting
  libraries.
- **Dependencies:** `P6-09`.
- **Acceptance criteria:** Episode list and detail render authoritative data
  with loading/empty/error states; Chinese-first labels per the existing
  presentation contract; persisted English content displayed as-is.
- **Required tests:** component/unit tests where useful; browser E2E coverage
  in `P6-15`.
- **Migration permission:** NONE.
- **Route-back conditions:** Missing data in the API routes back to `P6-08`.
- **Stop conditions:** Page validated and committed.

### P6-11 — Longitudinal Progress UX

- **Purpose:** `/progress` page presenting per-skill L2 patterns and the L3
  profile (trend, persistent gap, counts, current estimate vs target) using
  existing React/CSS/simple SVG; no charting library.
- **Scope:** New Next.js page and components under `web/src/app/progress/`;
  presentation only.
- **Allowed files:** `web/src/app/progress/**`, `web/src/components/**`,
  `web/src/lib/presentation.ts`.
- **Forbidden scope:** Backend changes, charting libraries, state
  recomputation, machine translation of persisted content.
- **Dependencies:** `P6-09`.
- **Acceptance criteria:** Trend/persistent-gap presentation matches the
  frozen semantics; `insufficient_history` presented clearly; drill-down to
  source episodes where available; Chinese-first.
- **Required tests:** unit tests where useful; browser E2E coverage in
  `P6-15`.
- **Migration permission:** NONE.
- **Route-back conditions:** Semantics mismatches route back to `P6-02`/
  `P6-08`.
- **Stop conditions:** Page validated and committed.

### P6-12 — Resume Learning Context

- **Purpose:** Dashboard resume section using `GET .../writing/context`:
  render current state, latest recommendation, latest relevant practice and
  its lifecycle, and the deterministic server-authoritative resume action;
  browser storage remains only an identity hint.
- **Scope:** Dashboard additions and context presentation components.
- **Allowed files:** `web/src/app/dashboard/**`, `web/src/components/**`,
  `web/src/lib/presentation.ts`.
- **Forbidden scope:** Authentication, account discovery, identity recovery,
  automatic next-practice generation, backend changes.
- **Dependencies:** `P6-09`.
- **Acceptance criteria:** Resume action reflects the server's authoritative
  context using only persisted learner-owned data. Submitted targeted
  practices are learner-owned through `WritingPractice` and recoverable before
  complete/apply. An unapplied initial `WritingEvaluation` identity is NOT
  recoverable from `learner_id` alone; when browser/client state carrying that
  identity is lost before apply, context falls back to `initial_writing`.
  No fabricated practice generation. No new ownership table is introduced to
  close the resume v1 limitation.
- **Required tests:** unit tests where useful; browser E2E coverage in
  `P6-15`.
- **Migration permission:** NONE.
- **Route-back conditions:** Resume-action mismatches route back to `P6-08`.
- **Stop conditions:** Resume UX validated and committed.

### P6-13 — Progressive Disclosure / Provenance UX

- **Purpose:** Present memory progressively: summary first, drill-down on
  demand (profile → patterns → atoms → episode → raw evaluation/attempt);
  expose provenance (source ids/evidence ids) in developer/audit views without
  leaking raw identifiers to learners in normal UI.
- **Scope:** Drill-down interactions and provenance presentation across
  `/history`, `/progress`, and episode detail.
- **Allowed files:** `web/src/app/**`, `web/src/components/**`,
  `web/src/lib/presentation.ts`.
- **Forbidden scope:** Backend changes, pushing essays/evaluations into
  default context, exposing raw database ids in learner-facing copy.
- **Dependencies:** `P6-10`, `P6-11`.
- **Acceptance criteria:** Each disclosure level reachable; raw source content
  only on explicit episode detail; no default LLM/Agent context includes full
  history.
- **Required tests:** unit tests where useful; browser E2E coverage in
  `P6-15`.
- **Migration permission:** NONE.
- **Route-back conditions:** Disclosure gaps route back to `P6-08` or
  `P6-02`.
- **Stop conditions:** UX validated and committed.

### P6-14 — Resilience / Chinese Presentation / Accessibility

- **Purpose:** Complete loading/empty/success/validation/provider/persistence
  states for all new pages; stable error-code mapping; Chinese-first copy;
  accessibility (focus, aria, keyboard, contrast).
- **Scope:** Cross-cutting presentation hardening for `P6-10`..`P6-13`.
- **Allowed files:** `web/src/**`, `web/tests/**`.
- **Forbidden scope:** Backend changes, new dependencies, non-Chinese primary
  UI.
- **Dependencies:** `P6-10`, `P6-11`, `P6-12`, `P6-13`.
- **Acceptance criteria:** Every remote view/action has distinct states;
  recognized codes map to Chinese copy; unknown failures get one generic
  recovery message; a11y checks pass.
- **Required tests:** unit tests, lint, typecheck, build, browser E2E in
  `P6-15`.
- **Migration permission:** NONE.
- **Route-back conditions:** Unmappable errors route back to `P6-08`.
- **Stop conditions:** Hardening validated and committed.

### P6-15 — Backend + Frontend + Browser E2E / CI

- **Purpose:** Full validation: backend pytest suite, frontend lint/typecheck/
  unit/build, and a Playwright browser E2E proving history, progress, and
  resume context against FastAPI + isolated PostgreSQL with deterministic
  fakes; CI gate.
- **Scope:** Tests, CI workflow updates, `web/e2e/` additions.
- **Allowed files:** `tests/`, `web/tests/`, `web/e2e/`, `.github/workflows/ci.yml`.
- **Forbidden scope:** Production code changes unrelated to test fixes, live
  DeepSeek calls in CI.
- **Dependencies:** `P6-10`..`P6-14`.
- **Acceptance criteria:** `python -m pytest -q --strict-markers` passes;
  `npm --prefix web run lint|typecheck|test|build` pass; Playwright E2E passes
  (no live provider); CI enforces all gates.
- **Required tests:** As listed in the acceptance criteria.
- **Migration permission:** NONE.
- **Route-back conditions:** Any failure routes back to the owning node.
- **Stop conditions:** All gates green.

### P6-16 — Internal Final Audit

- **Purpose:** Audit the completed graph: node statuses, evidence, tests,
  provenance invariants, scope compliance (no planner change, no vector DB, no
  RAG, no LangGraph, no multi-agent, no TencentDB dependency, no Phase 7).
- **Scope:** Audit report inside `docs/PHASE6_AUDIT.md` (new doc), final
  status update in this graph and `AGENTS.md`.
- **Allowed files:** `docs/PHASE6_AUDIT.md`, `docs/PHASE6_GRAPH.md`,
  `AGENTS.md`.
- **Forbidden scope:** New features, migrations, scope expansion.
- **Dependencies:** `P6-15` and all prior nodes.
- **Acceptance criteria:** Audit documents every node COMPLETE; evidence
  collected; handoff report produced; statuses updated truthfully.
- **Required tests:** Re-run of the full validation gates.
- **Migration permission:** NONE.
- **Route-back conditions:** Any finding routes back to its owning node.
- **Stop conditions:** `P6-16 = INTERNAL_AUDIT_COMPLETE`; report `STOP`;
  await External Review. Phase 7 must not start.

---

## 6. Scope and stop condition

In scope for Phase 6 (future execution): memory read-model schemas, L0 episode
query layer, L1 atom derivation, L2 pattern engine, L3 profile read model, the
four frozen read APIs, typed web integration, `/history` and `/progress` UX,
resume-context UX, progressive-disclosure/provenance UX, resilience, browser
E2E/CI, and the internal audit.

Out of scope: authentication, payments, Reading/Listening/Speaking, RAG/vector
storage/semantic memory, LangGraph or multi-agent runtime, Redis/Celery/Kafka,
pgvector/Milvus/Qdrant/Elasticsearch/BM25, embedding models, TencentDB Agent
Memory as a dependency, planner changes (`writing-practice-gap-v1` unchanged),
`LearnerSkillState` replacement, production deployment architecture.

Final stop condition for the Phase 6 execution run: `P6-01..P6-16 = COMPLETE`
(with `P6-16 = INTERNAL_AUDIT_COMPLETE`), External Review approved, then
`STOP`. Phase 7 remains NOT_STARTED and requires separate explicit authority
and its own graph.

---

## 7. Final status (after internal audit)

```text
P6-01 = COMPLETE
P6-02 = COMPLETE
P6-03 = COMPLETE
P6-04 = COMPLETE
P6-05 = COMPLETE
P6-06 = COMPLETE
P6-07 = COMPLETE
P6-08 = COMPLETE
P6-09 = COMPLETE
P6-10 = COMPLETE
P6-11 = COMPLETE
P6-12 = COMPLETE
P6-13 = COMPLETE
P6-14 = COMPLETE
P6-15 = COMPLETE
P6-16 = INTERNAL_AUDIT_COMPLETE
Phase 6 = INTERNAL_AUDIT_COMPLETE
External Review = PENDING
Phase 7 = NOT_STARTED
```

Phase 6 implementation exists on this branch per [PHASE6_AUDIT.md](PHASE6_AUDIT.md).
STOP — awaiting external review; Phase 7 must not start.
