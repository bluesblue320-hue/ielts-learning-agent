# Phase 7 Graph — Memory-Aware Adaptive Planning v2

## Document status

**DESIGN ACTIVE — P7-01 and P7-02 are COMPLETE; P7-03 through P7-14 are NOT_STARTED.**

This graph was created on `phase/7-memory-aware-planning-v2` from verified
`master` commit `fa34dc3499ab85e286340582353482c4b7388198` (`docs: finalize
Phase 6 merged status`). This run is authorized for design and baseline work
only. No application code, frontend code, migration, or test may be changed
until a later node is explicitly authorized.

Phase 7 evolves only the deterministic Writing planner. It is not a Core Agent
runtime, LLM planner, RAG/semantic-memory feature, vector database, TencentDB
runtime, multi-agent system, or expansion to another IELTS skill.

## Goal

```text
authoritative current learner state
  + deterministic longitudinal Writing memory
  -> memory-aware planner v2
  -> one auditable next-practice recommendation
```

Current state remains authoritative. Memory is permitted only to break an
**exact tie** between otherwise equally largest positive target gaps. A uniquely
largest positive target gap must always win, and all v1 no-practice branches
remain unchanged.

## Dependency graph

```text
START
  -> P7-01 Baseline & Memory-Aware Planning Capability Audit [COMPLETE]
  -> P7-02 Memory-Aware Planner v2 Contract Freeze [COMPLETE]
  -> P7-03 Versioned Planner v2 Schemas + Context Contract
  -> P7-04 Planner Persistence Evolution / Migration
  -> P7-05 Decision-Time Memory Context Builder
  -> P7-06 Deterministic Planner v2 Engine
  -> P7-07 Atomic Learning-Application Integration
  -> P7-08 Mixed v1/v2 Reconstruction & Backward Compatibility
  -> P7-09 Planning Explanation API Contract
  -> P7-10 Memory-Aware Recommendation UX
  -> P7-11 Context / Practice Lifecycle Compatibility
  -> P7-12 Concurrency / Idempotency / Migration Hardening
  -> P7-13 Backend + Frontend + Browser E2E / CI
  -> P7-14 Internal Final Audit
  -> STOP -> External Review
```

Nodes activate only after every dependency is complete and after explicit
authority for implementation. P7-03 and later are not authorized by this run.

## P7-01 — Baseline & Memory-Aware Planning Capability Audit — COMPLETE

### Evidence inspected

The audit reconciled `AGENTS.md`, `README.md`, `docs/ARCHITECTURE.md`,
`docs/DEVELOPMENT_LOOP.md`, `PRACTICE_PLANNING_POLICY.md`,
`WRITING_STATE_POLICY.md`, `WRITING_MEMORY_POLICY.md`, `PHASE6_GRAPH.md`, and
`PHASE6_AUDIT.md` with the actual implementation. It inspected the requested
learner, memory, schema, persistence, service, route, web-client, dashboard,
progress, planner, API, concurrency, memory, practice, and E2E tests.

### Audit answers

1. **Where v1 is called.** `apply_writing_evaluation` in
   `app/services/learning_application.py` calls `plan_practice` after it
   flushes four immutable `LearningEvidence` rows and rebuilds all four
   materialized state rows. It is the common path for initial evaluation apply
   and `PracticeCompletionService.complete`, which delegates to the same
   service.
2. **v1 assumptions.** `planning_policy.PLANNER_VERSION`, `planner.py`, and
   `PracticeRecommendationDecision` are v1-specific. The schema makes
   `planner_version` `Literal["writing-practice-gap-v1"]` and admits only five
   frozen no-practice or four frozen practice reason-code sequences.
   `learning_application._reconstruct_decision` and
   `memory.episode_queries.reconstruct_decision` unconditionally reconstruct
   that schema. `PracticeRecommendation` stores one recommendation per update
   and only a `state_snapshot`.
3. **Persistence constraints.** `practice_recommendations` has JSONB
   `reason_codes` and `state_snapshot`; PostgreSQL validates its v1 reason
   sequences, decision shape, target-band nullability, and four state keys.
   `LearningUpdate.planner_version` and `PracticeRecommendation.planner_version`
   are nonblank strings, not v1 literals. Thus they can record v2 without a
   column change, but v2 context cannot be stored today.
4. **Safe transaction-time Memory derivation.** Yes. Under the existing
   per-learner `FOR UPDATE` lock, the apply service flushes its new evidence,
   reads the complete accepted evidence set, and reconstructs states before
   planning. Phase 6 reads use only the same session and durable rows;
   SQLAlchemy can read its own flushes. Reusable pure policy functions are
   `compute_trend`, `compute_persistent_gap`, and the episode-window practice
   counters. A future planner-owned builder must use those domain primitives,
   not call an HTTP route or consume `WritingProgressResponse`.
5. **Safe inputs.** The minimum deterministic inputs are each skill's
   `trend`, `persistent_gap`, `persistent_gap_status`, and
   `recent_practice_count`, with `writing-memory-v1`, `writing-progress-v1`,
   and source observation/episode/practice-window ids for provenance. Current
   state, target, evidence count, and state snapshot remain planner inputs
   owned by Phase 3, not Memory substitutes.
6. **Excluded inputs.** Raw essays/questions, feedback, strengths, weaknesses,
   error tags, recommended skills, provider/model metadata, free-form prompts,
   and any LLM reasoning remain excluded. They are qualitative L0 evidence,
   not frozen planning facts.
7. **Historical reconstruction.** No: `state_snapshot` cannot reconstruct the
   v2 decision context. Future evidence can change trend and persistent-gap
   windows; future completed practices can change recent-practice counts;
   late-arriving old evidence can alter canonical windows. Recomputing today's
   progress therefore cannot answer why a historical decision was made.
8. **Persistence decision.** A migration is required. The minimal change is
   an additive nullable `planner_context_snapshot JSONB` on
   `PracticeRecommendation`, checked as `NULL` or a JSON object. v1 rows stay
   `NULL`; v2 rows must carry a strict, versioned snapshot through the v2
   Pydantic/domain contract. No new table is justified.
9. **Reason codes.** Keep the existing taxonomy and database sequences. v2
   continues to use `largest_target_gap`; it adds `priority_tiebreak` only when
   final canonical priority actually selects among unresolved candidates.
   Memory selection is documented in the persisted structured trace, not
   encoded as cosmetic new reason codes. Existing constraints therefore remain
   semantically correct and need no reason-code expansion.
10. **Schema coexistence.** Keep a strict v1 decision model and add a strict
    v2 decision model, selected by discriminated `planner_version`. Public
    APIs and reconstruction paths must use their discriminated union; existing
    v1 imports may retain a v1 compatibility alias during the implementation.
    A single conditionally widened v1 model is rejected because it would make
    a historically frozen contract ambiguous.
11. **Selection trace.** Required. The snapshot needs a compact deterministic
    trace of the exact maximum-gap candidate set, each considered tie-break
    stage and whether it narrowed the set, final candidates, and selected
    skill. The trace complements—rather than duplicates—the persisted context.
12. **Late arrival.** Evidence ordering remains the frozen canonical
    `(source_created_at ASC, source_attempt_id ASC)` order. The context is
    computed after the new evidence is flushed, so the newly accepted evidence
    participates immediately, including when it is chronologically older.
    Recent-practice counting remains Phase 6's latest three learner-owned L0
    episodes by `(LearningUpdate.created_at DESC, id DESC)` and counts only
    completed targeted practices. The persisted snapshot, rather than a later
    recomputation, is authoritative for the historical v2 decision.
13. **Mixed history/API impact.** History detail and context currently rebuild
    a v1-only decision, and the typed web client represents an unversioned
    recommendation. P7-08/P7-09 must reconstruct a discriminated v1/v2 union
    and expose only a safe structured v2 explanation derived from the stored
    trace. The dashboard/history presentation needs a new v2 explanation
    branch; progress itself is already an appropriate read source but is not
    the historical explanation source.
14. **Practice-generation impact.** No generator policy or prompt change is
    needed. Practice generation already accepts a persisted recommendation and
    consumes target skill, target band, reasons, and planner version. It must
    remain agnostic to Memory and never receive the context snapshot.
15. **Tests required later.** Preserve every v1 planner/schema/API/history/
    practice test. Add v2 pure-engine matrices, strict schema and migration
    tests, context provenance/reconstruction tests, canonical-order late-arrival
    tests, atomic apply/idempotency/concurrency tests, mixed-history API tests,
    typed-client tests, dashboard explanation tests, and Chromium E2E for a
    persisted v2 explanation. Tests are forbidden in this design run.

### P7-01 conclusion

`writing-practice-gap-memory-v2` is feasible as a deterministic, conservative
planner. It requires one narrow additive migration, a planner-owned context
builder, strict versioned decision schemas, and a persisted decision-time
snapshot. It does not require a new table, provider call, generator change,
or frontend change until later authorized nodes.

## Implementation node definitions — NOT AUTHORIZED

Each node below specifies future scope only. `allowed files` are inclusive;
the Phase 7 global exclusions (LLM planner, agent runtime, vectors/RAG,
TencentDB, and non-Writing skills) apply to every node.

### P7-02 — Memory-Aware Planner v2 Contract Freeze

- **Purpose/scope:** Freeze the policy document and this graph from P7-01.
- **Dependencies:** P7-01.
- **Allowed files:** `docs/MEMORY_AWARE_PLANNING_POLICY.md`, this graph,
  `AGENTS.md`, and status-only `README.md`/`docs/ARCHITECTURE.md`.
- **Forbidden scope:** all runtime, frontend, migration, and test files.
- **Acceptance/tests:** a reviewable normative contract with examples; Markdown
  and diff checks only.
- **Migration permission:** no.
- **Route-back/stop:** route back to P7-01 if the contract discovers an
  uninspected dependency; stop after the frozen design contract pending review.

### P7-03 — Versioned Planner v2 Schemas + Context Contract

- **Purpose/scope:** Add strict v1/v2 discriminated decisions and planner-owned
  context/trace schemas.
- **Dependencies:** P7-02.
- **Allowed files:** `app/schemas/planning.py`, a focused planning schema module
  if needed, imports, and schema tests.
- **Forbidden scope:** ORM/migration, engine, service, route, generator, web.
- **Acceptance/tests:** v1 validation remains byte-for-byte semantic; v2
  rejects missing/malformed context and noncanonical trace; schema tests pass.
- **Migration permission:** no.
- **Route-back/stop:** return to P7-02 for any contract ambiguity; stop before
  persistence or engine work.

### P7-04 — Planner Persistence Evolution / Migration

- **Purpose/scope:** Add only nullable `planner_context_snapshot` to
  `practice_recommendations` and an object/null database check.
- **Dependencies:** P7-03.
- **Allowed files:** `app/models/learning.py`, one Alembic revision, migration
  and persistence-model tests.
- **Forbidden scope:** planner algorithm, service integration, APIs, web, new
  table, rewrite of historical recommendations.
- **Acceptance/tests:** upgrade/downgrade is reversible; v1 NULL rows persist;
  JSON object shape is protected; current constraints remain valid.
- **Migration permission:** yes, narrow additive only.
- **Route-back/stop:** return to P7-02 if a new table or non-additive migration
  appears necessary; stop after migration validation.

### P7-05 — Decision-Time Memory Context Builder

- **Purpose/scope:** Build planner-owned deterministic context from one session
  after evidence/state flush, reusing Phase 6 domain primitives.
- **Dependencies:** P7-03, P7-04.
- **Allowed files:** focused `app/learner/` context module, narrow imports, and
  unit tests.
- **Forbidden scope:** routes, HTTP response coupling, provider calls, web,
  persistence writes other than P7-04.
- **Acceptance/tests:** canonical ordering, immediate new-evidence inclusion,
  correct recent-practice episode window, four-skill provenance, repeatability.
- **Migration permission:** no.
- **Route-back/stop:** return to P7-01 if Session visibility disproves the
  audit; stop before selection logic.

### P7-06 — Deterministic Planner v2 Engine

- **Purpose/scope:** Implement pure v2 current-gap-first selection and trace.
- **Dependencies:** P7-03, P7-05.
- **Allowed files:** planner v2/policy modules and unit tests.
- **Forbidden scope:** v1 algorithm changes, ORM, service, routes, web,
  weighting heuristics, LLM calls.
- **Acceptance/tests:** all frozen examples, reordered logical inputs, unique
  maximum-gap non-override, and exact reason-code semantics pass.
- **Migration permission:** no.
- **Route-back/stop:** return to P7-02 for policy ambiguity; stop before apply
  integration.

### P7-07 — Atomic Learning-Application Integration

- **Purpose/scope:** Select v2, persist its context, and reconstruct it inside
  the existing one-transaction apply path.
- **Dependencies:** P7-04, P7-05, P7-06.
- **Allowed files:** learning-application service, focused tests and imports.
- **Forbidden scope:** provider calls in the transaction, separate transaction,
  generator policy/prompt changes, routes/web.
- **Acceptance/tests:** one update/four evidence/four states/one recommendation;
  rollback and idempotency preserve exactly one context-bearing v2 row.
- **Migration permission:** no.
- **Route-back/stop:** return to P7-05 on transaction-read issues; stop before
  public mixed-version reconstruction.

### P7-08 — Mixed v1/v2 Reconstruction & Backward Compatibility

- **Purpose/scope:** Reconstruct persisted v1 and v2 decisions without
  reinterpretation and retain old history usability.
- **Dependencies:** P7-03, P7-04, P7-07.
- **Allowed files:** reconstruction/query modules, schemas, focused tests.
- **Forbidden scope:** rewriting historical rows, planner policy changes, web.
- **Acceptance/tests:** old v1 fixture/recommendation validates unchanged; v2
  validates only with snapshot; mixed histories return both correctly.
- **Migration permission:** no.
- **Route-back/stop:** return to P7-03 if union design fails; stop before new
  explanation response contract.

### P7-09 — Planning Explanation API Contract

- **Purpose/scope:** Expose a safe persisted v2 explanation alongside existing
  recommendation reads.
- **Dependencies:** P7-08.
- **Allowed files:** schemas, learner/memory routes/query services, API tests.
- **Forbidden scope:** LLM explanation, raw database ids in user-facing fields,
  generator, web.
- **Acceptance/tests:** historical v1 output remains valid; v2 explanation is
  strictly derived from its stored trace, never current progress recomputation.
- **Migration permission:** no.
- **Route-back/stop:** return to P7-08 for any lost reconstruction invariant;
  stop before UI.

### P7-10 — Memory-Aware Recommendation UX

- **Purpose/scope:** Render a Chinese-first, deterministic “why recommended”
  explanation for v2 and retain the v1 presentation.
- **Dependencies:** P7-09.
- **Allowed files:** `web/src/lib/api/client.ts`, presentation helpers, relevant
  dashboard/history components, frontend tests.
- **Forbidden scope:** backend policy changes, raw ids, free-form/LLM copy,
  broader redesign.
- **Acceptance/tests:** type-safe union handling, accessible v1/v2 fallbacks,
  no raw provenance ids, frontend tests pass.
- **Migration permission:** no.
- **Route-back/stop:** return to P7-09 for unavailable persisted explanation;
  stop before lifecycle changes.

### P7-11 — Context / Practice Lifecycle Compatibility

- **Purpose/scope:** Verify context/resume, generation, submission, and
  completion retain their Phase 4/6 behavior across both planner versions.
- **Dependencies:** P7-08, P7-09, P7-10.
- **Allowed files:** focused context/practice services/routes/client/tests.
- **Forbidden scope:** memory-conditioned practice prompts, lifecycle redesign,
  automatic practice generation.
- **Acceptance/tests:** one v1 and one v2 recommendation each resolve through
  generation and completion; resume remains server-authoritative.
- **Migration permission:** no.
- **Route-back/stop:** return to P7-08 on compatibility break; stop before
  hardening.

### P7-12 — Concurrency / Idempotency / Migration Hardening

- **Purpose/scope:** Prove v2 context persistence under races and migration
  edge cases.
- **Dependencies:** P7-04, P7-07, P7-11.
- **Allowed files:** focused service/migration tests and only minimal repairs.
- **Forbidden scope:** new locks, broad infrastructure, provider work, web
  features.
- **Acceptance/tests:** PostgreSQL concurrent apply/idempotency, rollback,
  late-arrival, upgrade/downgrade, and mixed-row tests pass.
- **Migration permission:** corrective only; no new unrelated revision.
- **Route-back/stop:** return to owner node for semantic failure; stop on any
  unbounded locking or new persistence requirement.

### P7-13 — Backend + Frontend + Browser E2E / CI

- **Purpose/scope:** Run and repair the bounded validation matrix.
- **Dependencies:** P7-12.
- **Allowed files:** tests, E2E, CI only when required by a demonstrated test
  issue, and minimal owning-code repairs.
- **Forbidden scope:** feature expansion, policy alteration to satisfy tests.
- **Acceptance/tests:** targeted unit/API/PostgreSQL/migration/frontend and
  Chromium v1/v2 paths plus relevant full suites pass.
- **Migration permission:** no.
- **Route-back/stop:** route failures to their owning node; stop after clean
  evidence or an external-environment blocker.

### P7-14 — Internal Final Audit

- **Purpose/scope:** Reconcile final code, schema, migration, docs, tests, and
  phase boundaries before external review.
- **Dependencies:** P7-13.
- **Allowed files:** audit/status documentation and minimal documentation fixes.
- **Forbidden scope:** new features, schema changes, migrations, Phase 8.
- **Acceptance/tests:** fresh validation evidence, exact commit/file inventory,
  v1 preservation, and explicit exclusions documented.
- **Migration permission:** no.
- **Route-back/stop:** route any defect to its owner; otherwise stop for
  external review.

## Current phase status

```text
Phase 1 = COMPLETE
Phase 2 = COMPLETE
Phase 3 = COMPLETE
Phase 4 = COMPLETE
Phase 5 = COMPLETE
Phase 6 = COMPLETE
Phase 7 = DESIGN_ACTIVE
P7-01 = COMPLETE
P7-02 = COMPLETE
P7-03 = NOT_STARTED
Phase 8 = NOT_STARTED
```
