# Phase 7 Graph — Memory-Aware Adaptive Planning v2

## Document status

**IMPLEMENTATION_ACTIVE — External Design Review is APPROVED. P7-01 through P7-05 are COMPLETE; P7-06 through P7-14 are NOT_STARTED.**

This graph was created on `phase/7-memory-aware-planning-v2` from verified
`master` commit `fa34dc3499ab85e286340582353482c4b7388198` (`docs: finalize
Phase 6 merged status`). External Design Review has approved continuous execution from P7-03 through P7-14, with each node remaining a mandatory quality gate. No Phase 8 work, master merge, or pull request is authorized before external implementation review.

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
  -> P7-03 Versioned Planner v2 Schemas + Context Contract [COMPLETE]
  -> P7-04 Planner Persistence Evolution / Migration [COMPLETE]
  -> P7-05 Decision-Time Memory Context Builder [COMPLETE]
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

Nodes activate only after every dependency is complete. External Design Review has authorized continuous implementation through P7-14; each node is still a mandatory commit, test, and push checkpoint.

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
4. **Safe transaction-time derivation and query boundary.** Deterministic Memory can be computed in the existing apply transaction after the new update/evidence flush and state rebuild. Trend/gap may reuse pure Phase 6 policy functions. Recency MUST NOT call `list_learner_episodes()`: that query inner-joins a recommendation that does not yet exist. P7-05 needs a planner-owned pre-recommendation projection over `LearningUpdate -> WritingEvaluation -> WritingAttempt -> optional WritingPractice`, ordered by accepted-update `LearningUpdate.id DESC`. Memory context is built lazily only after base selection detects an exact tie.
5. **Safe inputs.** Per skill: `trend`, `persistent_gap`, `persistent_gap_status`, `recent_practice_count`, plus Memory/progress/context versions and ordered source observation/episode/practice-window ids. Recent-practice count is a Phase 7 planner-owned accepted-update signal, not Phase 6 public progress recency. Current target/state remain separate Phase 3 planner inputs.
6. **Excluded inputs.** Raw essays/questions, feedback, strengths, weaknesses, error tags, recommended skills, provider/model metadata, prompts, and LLM reasoning remain excluded.
7. **Historical reconstruction.** It is possible when bounded by recommendation owner `LearningUpdate U`. Same-learner apply transactions acquire the learner lock before inserting updates, so committed same-learner rows with `id <= U.id` are the decision-time accepted set. Restrict evidence to that set and canonically order it to rebuild trend/gap; order accepted rows by `id DESC`, limit to the planning window, and project actual practice targets to rebuild recency. Later-applied old evidence has a later owning-update id and is excluded. U's recommendation target and state snapshot provide the other exact inputs.
8. **Persistence decision and tradeoff.** Keep one additive nullable `planner_context_snapshot JSONB`, not because reconstruction is impossible, but as an intentional immutable decision-time audit snapshot. Authoritative-row reconstruction remains an audit verification path. The snapshot is required only for a v2 exact-tie practice decision; it is NULL for v1, v2 no-practice, and v2 unique-gap decisions. No new table is justified.
9. **Reason codes.** Keep the v1 taxonomy/sequences. `priority_tiebreak` appears iff final canonical priority actually narrows an unresolved tie; Memory stages never add it.
10. **Schema coexistence.** Preserve strict v1/v2 decisions discriminated by `planner_version`, but separate planner input `MemoryAwarePlanningContext`, output `PlannerSelectionTrace`, and persisted `PersistedPlannerContextSnapshot`. The full audit envelope is internal and is not the normal public recommendation schema.
11. **Selection trace.** Required only for exact-tie practice decisions. It is planner output, not context input. It records canonical candidate lists and considered stages; a non-narrowing stage has identical before/after lists, never an empty filtered output.
12. **Late arrival and recency.** Newly flushed evidence participates immediately under canonical source order. A minimal `PlanningPracticeEpisode` query includes the current flushed update without requiring a recommendation, uses planner-owned accepted-update `id DESC` order, lets initial writing occupy a slot, and counts a targeted completion against actual `WritingPractice.target_skill`. Stored exact-tie snapshots remain immutable.
13. **Mixed history/API impact.** Internal reconstruction validates optional conditional audit envelopes for v1/v2 rows. Normal product responses expose existing decision fields, version, and a safe `planning_explanation` derived from the persisted historical trace—never current progress or raw provenance ids. Any developer audit surface must be separate.
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
planner. It requires one narrow additive migration, a planner-owned context builder with a pre-recommendation recency query, strict versioned decision schemas, and a conditional immutable audit snapshot for exact ties. It does not require a new table, provider call, generator change,
or frontend change until later authorized nodes.

## Implementation node definitions — NOT AUTHORIZED

Each node below specifies future scope only. `allowed files` are inclusive;
the Phase 7 global exclusions (LLM planner, agent runtime, vectors/RAG,
TencentDB, and non-Writing skills) apply to every node.

### P7-02 — Memory-Aware Planner v2 Contract Freeze — COMPLETE

- **Purpose/scope:** Freeze and repair the policy document and this graph from P7-01; delivered by `MEMORY_AWARE_PLANNING_POLICY.md`.
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

- **Purpose/scope:** Add strict v1/v2 decisions plus separate input
  `MemoryAwarePlanningContext`, output `PlannerSelectionTrace`, conditional
  `PersistedPlannerContextSnapshot`, and public explanation schemas.
- **Dependencies:** P7-02.
- **Allowed files:** focused planning schema modules, imports, and schema tests.
- **Forbidden scope:** ORM/migration, engine, service, route, generator, web.
- **Acceptance/tests:** v1 semantics stay frozen; input context cannot contain
  trace; exact-tie output trace is canonical; conditional snapshot presence and
  public/internal separation validate.
- **Migration permission:** no.
- **Route-back/stop:** return to P7-02 for ambiguity; stop before persistence.

### P7-04 — Planner Persistence Evolution / Migration

- **Purpose/scope:** Add nullable `planner_context_snapshot` with an object/null
  check to the existing recommendation table.
- **Dependencies:** P7-03.
- **Allowed files:** `app/models/learning.py`, one Alembic revision, and focused
  migration/model tests.
- **Forbidden scope:** algorithm, services, APIs, web, new table, old-row rewrite.
- **Acceptance/tests:** reversible upgrade/downgrade; v1, v2 no-practice, and v2
  unique-gap rows accept NULL; v2 exact-tie practice requires the strict audit
  envelope; existing reason constraints remain valid.
- **Migration permission:** yes, narrow additive only.
- **Route-back/stop:** return to P7-02 if non-additive storage is required.

### P7-05 — Decision-Time Memory Context Builder

- **Purpose/scope:** Build context only for an exact tie, using a minimal pre-recommendation projection and planner-owned accepted-update recency.
- **Dependencies:** P7-03, P7-04.
- **Allowed files:** focused `app/learner/` context/query module, policy constants, and unit tests.
- **Forbidden scope:** `list_learner_episodes()`, PracticeRecommendation joins, created-at planner recency, routes, HTTP response coupling, provider calls, web, persistence writes, or Phase 6 progress changes.
- **Acceptance/tests:** `PLANNING_RECENT_PRACTICE_WINDOW = 3`; same-learner `LearningUpdate.id DESC`; current flushed update first; initial writing occupies a slot; targeted completion counts actual practice target; historical owner-U reconstruction uses `id <= U.id`, `id DESC`, and the same limit.
- **Migration permission:** no.
- **Route-back/stop:** return to P7-01 if accepted-update identity ordering is disproven; stop before tie resolution.

### P7-06 — Deterministic Planner v2 Engine

- **Purpose/scope:** Implement base selection first and the pure Memory tie resolver second.
- **Dependencies:** P7-03, P7-05.
- **Allowed files:** planner v2/policy modules and unit tests.
- **Forbidden scope:** requiring Memory context for no-practice or unique-gap decisions, v1 changes, ORM, services, routes, web, weights, or LLM calls.
- **Acceptance/tests:** no-practice and unique-gap outcomes require no context; `MemoryAwarePlanningContext` is required iff exact maximum-gap candidate count is greater than one; frozen tie hierarchy/trace and reordered-input determinism pass.
- **Migration permission:** no.
- **Route-back/stop:** return to P7-02 for policy ambiguity; stop before apply integration.

### P7-07 — Atomic Learning-Application Integration

- **Purpose/scope:** Activate v2 for every new apply; perform base selection first; lazily build/persist Memory context only for an exact tie.
- **Dependencies:** P7-04, P7-05, P7-06.
- **Allowed files:** learning-application service, focused tests and imports.
- **Forbidden scope:** any Memory query for no-practice/unique-gap branches, provider call, separate transaction, request version selector, feature flag, historical rewrite, generator prompt change, or web.
- **Acceptance/tests:** irrelevant Memory failure cannot block no-practice/unique-gap results; exact tie uses the current id-ordered window and conditional envelope; rollback/idempotency preserve the original version and decision.
- **Migration permission:** no.
- **Route-back/stop:** return to P7-05 on accepted-update query issues.

### P7-08 — Mixed v1/v2 Reconstruction & Backward Compatibility

- **Purpose/scope:** Reconstruct mixed v1/v2 decisions and conditional internal
  audit envelopes without rewriting history; project a separate public decision.
- **Dependencies:** P7-03, P7-04, P7-07.
- **Allowed files:** reconstruction/query modules, schemas, focused tests.
- **Forbidden scope:** old-row rewrite, public raw audit envelope, policy change.
- **Acceptance/tests:** v1 validates unchanged; v2 NULL/envelope cases follow the
  presence matrix; mixed history returns correct internal and public shapes.
- **Migration permission:** no.
- **Route-back/stop:** return to P7-03 if version dispatch is ambiguous.

### P7-09 — Planning Explanation API Contract

- **Purpose/scope:** Derive safe public v2 `planning_explanation` from the
  persisted historical trace and define any developer audit surface separately.
- **Dependencies:** P7-08.
- **Allowed files:** schemas, learner/memory query/routes, API tests.
- **Forbidden scope:** raw envelope/provenance ids in normal recommendation
  fields, current-progress recomputation, LLM explanation, generator, web.
- **Acceptance/tests:** v1 and v2 non-tie output remains valid; relevant v2
  explanation reflects only stages from its stored trace.
- **Migration permission:** no.
- **Route-back/stop:** return to P7-08 for a reconstruction invariant failure.

### P7-10 — Memory-Aware Recommendation UX

- **Purpose/scope:** Render the safe Chinese-first `planning_explanation` for a
  relevant v2 exact tie and retain v1/unique-gap/no-practice presentation.
- **Dependencies:** P7-09.
- **Allowed files:** typed client, presentation helpers, relevant UI/tests.
- **Forbidden scope:** backend policy, raw ids/envelope, LLM copy, redesign.
- **Acceptance/tests:** type-safe version handling, accessible fallbacks, no raw
  provenance, frontend tests pass.
- **Migration permission:** no.
- **Route-back/stop:** return to P7-09 if safe explanation is unavailable.

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

- **Purpose/scope:** Prove conditional context persistence and accepted-update recency under races and migration edge cases.
- **Dependencies:** P7-04, P7-07, P7-11.
- **Allowed files:** focused service/migration tests and minimal repairs.
- **Forbidden scope:** new locks, broad infrastructure, provider work, web features, or Phase 6 recency changes.
- **Acceptance/tests:** same-learner transactions whose start order differs from update insertion/acceptance order still place the current update first by id; owner-U reconstruction matches `id <= U.id`, `id DESC`, LIMIT 3; lazy no-practice/unique-gap paths avoid Memory queries; PostgreSQL idempotency, rollback, late arrival, migration, and mixed rows pass.
- **Migration permission:** corrective only; no unrelated revision.
- **Route-back/stop:** return failures to the owning node; stop on unbounded locking or new storage need.

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
Phase 7 = IMPLEMENTATION_ACTIVE
P7-01 = COMPLETE
P7-02 = COMPLETE
P7-03 = COMPLETE
P7-04 = COMPLETE
P7-05 = COMPLETE
P7-06 = NOT_STARTED
Phase 8 = NOT_STARTED
```
