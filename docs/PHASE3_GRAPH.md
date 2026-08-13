# Phase 3 Development Graph

## Purpose and authority

This document defines **what** may be implemented in Phase 3 and the dependency
order for Learner State & Adaptive Planning. [DEVELOPMENT_LOOP.md](DEVELOPMENT_LOOP.md)
defines **how** to execute each selected node. The completed
[PHASE1_GRAPH.md](PHASE1_GRAPH.md) and [PHASE2_GRAPH.md](PHASE2_GRAPH.md) remain
historical execution records.

Phase 3 is based on merged Phase 2 commit
`dd63a99a9fc08cbe5597988f71aaa360a3a1f66c`, including the accepted Writing
Task 2 pipeline and Alembic head `0002_writing`. Creating and approving this
graph authorizes the Phase 3 scope, but does not activate a node or authorize
continuous execution by itself. `P3-01` is the first `READY` node. Every later
node is `NOT_STARTED` until all declared dependencies are `COMPLETE`.

## Phase objective

Phase 3 delivers one deterministic and auditable adaptive-learning path:

```text
Persisted Phase 2 WritingEvaluation
  -> LearningUpdate
  -> four immutable LearningEvidence observations
  -> four materialized LearnerSkillState rows
  -> deterministic Practice Planner
  -> persisted PracticeRecommendation
```

The phase must make it possible to answer:

1. What does the application currently believe about a learner's Writing
   ability?
2. Which historical evidence produced that state?
3. Which Writing skill should the learner practice next, and why?
4. Has a persisted Writing evaluation already been applied?
5. Can current learner state be rebuilt from the accepted evidence history?

Phase 3 consumes an **already persisted** Phase 2 `WritingEvaluation`. It does
not redesign the evaluator and never holds a Phase 3 transaction open while
calling DeepSeek or another provider.

## Core domain concepts

- **Learner:** minimal learning identity with a Writing target band. Phase 3
  adds no authentication or account system.
- **LearningUpdate:** the provenance and idempotency anchor for one successful
  application of one persisted `WritingEvaluation` to one learner.
- **LearningEvidence:** an immutable, append-only historical observation. One
  accepted Writing evaluation produces exactly four canonical observations.
- **LearnerSkillState:** the current materialized estimate derived from accepted
  evidence. It is not the historical source of truth.
- **PracticeRecommendation:** an immutable historical planning decision derived
  from learner state at a specific learning update.

The initial taxonomy is `writing-core-v1` and contains exactly:

- `task_response`
- `coherence_and_cohesion`
- `lexical_resource`
- `grammatical_range_and_accuracy`

Phase 2 free text—strengths, weaknesses, error tags, recommended skills, and
feedback—is not automatically converted into canonical learner-state
dimensions. Phase 3 v1 state is driven by the four structured criterion bands.

## Architecture and domain invariants

1. **Evidence is not state.** Evidence remains historical source-of-truth data;
   materialized state never replaces evidence history.
2. **Evidence is append-only.** Accepted evidence is not silently edited by
   normal update or rebuild operations.
3. **State is rebuildable.** Given the same accepted evidence, deterministic
   order, taxonomy version, and state-policy version, replay must reproduce the
   materialized state exactly.
4. **State updates are deterministic.** No LLM selects estimates, weights,
   confidence, evidence inclusion, precision, rounding, or recency behavior.
5. **Policy precedes implementation.** `P3-02` freezes the complete versioned
   state policy before `P3-07` implements it. This graph intentionally does not
   invent the numeric formula.
6. **Idempotency is database-backed.** The same persisted Writing evaluation
   affects Phase 3 at most once. Python-only existence checks are insufficient.
7. **Writing evaluation ownership is exclusive.** One `WritingEvaluation` may
   be applied to at most one learner. Cross-learner reuse is an explicit
   conflict.
8. **One evaluation yields four observations.** Partial extraction or partial
   application is invalid.
9. **Learning application is atomic.** Claiming the update, writing four
   evidence records, updating four state rows, and persisting one recommendation
   commit together or all roll back. The Phase 2 evaluation remains valid.
10. **No provider call occurs in the transaction.** Phase 3 reads persisted
    evaluation data only.
11. **Planning is deterministic.** `P3-08` freezes the policy before `P3-09`
    implements it. No LLM decides what to practice.
12. **Tie-breaking is explicit.** No implicit dictionary, ORM, or database row
    order may select a skill.
13. **Recommendations are auditable history.** A stored recommendation retains
    the learner target, relevant state snapshot, stable reason codes, source
    update, planner version, and decision-time values.
14. **Policies are versioned.** Phase 3 retains
    `skill_taxonomy_version`, `state_policy_version`, and `planner_version`;
    evidence provenance preserves relevant Phase 2 provider, model, prompt,
    rubric, scoring-policy, and thinking-mode identifiers.
15. **Concurrency is database-safe.** Process-local locks are not a correctness
    mechanism. PostgreSQL constraints, row locking, optimistic revision checks,
    or an equivalent database-safe design must protect concurrent updates.

## Conceptual persistence contract

Exact SQL types and indexes are selected by the owning node, but the relational
design must preserve these concepts and invariants:

- `Learner`: id, `writing_target_band`, `created_at`, `updated_at`.
- `LearningUpdate`: id, learner reference, unique Writing evaluation
  reference, taxonomy/state-policy/planner versions, `created_at`; it may serve
  as the idempotency and ownership anchor.
- `LearningEvidence`: id, update/learner/evaluation references, canonical
  `skill_key`, `observed_band`, required Phase 2 provenance, `created_at`;
  immutable after acceptance.
- `LearnerSkillState`: learner and skill key, `estimated_band`,
  `evidence_count`, policy version, `last_evidence_id`, `revision`, and
  `updated_at`; unique by learner and skill.
- `PracticeRecommendation`: id, learner/update references, target skill,
  learner target and estimate at decision time, reason codes, planner version,
  state snapshot, and `created_at`.

Confidence is omitted unless `P3-02` adopts a real deterministic mathematical
definition and `P3-08` explicitly defines whether and how the planner consumes
it. Decorative confidence is forbidden.

## Node states and deterministic selection

Each node has one state:

```text
NOT_STARTED -> READY -> ACTIVE -> VERIFYING -> COMPLETE
                         |          |
                         v          v
                       FIXING <-----+

Any state -> BLOCKED when required input or authority is unavailable.
```

A node becomes `READY` only when all declared dependencies are `COMPLETE`.
Only one mutating node may be `ACTIVE`. A failed acceptance gate keeps the
same node in `FIXING` and never unlocks downstream nodes.

Selection follows [DEVELOPMENT_LOOP.md](DEVELOPMENT_LOOP.md): use an explicitly
selected `READY` node; otherwise select the lowest-numbered `READY` node.
This graph's initial state is:

- `P3-01`: `READY`
- `P3-02` through `P3-15`: `NOT_STARTED`

This design-only task does not activate or execute `P3-01`.

## Dependency graph

```text
P3-01 Phase 3 Baseline & Transition
  -> P3-02 Writing Skill Taxonomy & State Update Policy

P3-02
  -> P3-03 Learner / Evidence / State Schemas
  -> P3-08 Practice Planning Policy

P3-03
  -> P3-04 Persistence Models

P3-04
  -> P3-05 Alembic Migration

P3-05
  -> P3-06 Writing Evidence Extraction

P3-06
  -> P3-07 Learner State Update Engine

P3-07 + P3-08
  -> P3-09 Practice Planner

P3-05 + P3-06 + P3-07 + P3-09
  -> P3-10 Learning Update Application Service

P3-10
  -> P3-11 Learner & Learning APIs

P3-11
  -> P3-12 Concurrency / Failure / Idempotency Hardening

P3-12
  -> P3-13 Automated & Integration Validation

P3-13
  -> P3-14 Docker & Documentation

P3-14
  -> P3-15 Final Phase Audit

P3-15 -> STOP
```

The node contracts below and this graph agree. No downstream node may start
early, even when its eventual code location is already known.

## Nodes and acceptance gates

### P3-01 — Phase 3 Baseline & Transition

- **Purpose:** Establish the accepted merged Phase 2 baseline and Phase 3
  execution authority without adding runtime behavior.
- **Dependencies:** Phase 2 `P2-15` complete; PR #6 merged into `master`; no
  Phase 3 node dependency.
- **Inputs:** Latest merged `master`, Phase 2 audit and CI result, Alembic
  history through `0002_writing`, accepted regression suite, this graph, and
  [DEVELOPMENT_LOOP.md](DEVELOPMENT_LOOP.md).
- **Deliverables:** Recorded Phase 2 merge/CI/regression baseline, confirmed
  single Alembic head, dedicated Phase 3 implementation branch, and confirmed
  Phase 3 documentation authority; no models, schemas, services, APIs, or
  migrations.
- **Required validation:** Verify local base equals current `origin/master`;
  inspect PR #6 merge and Phase 2 audit; run the accepted regression suite;
  inspect Alembic heads; confirm branch isolation and no Phase 3 runtime diff.
- **Acceptance condition:** Phase 2 is demonstrably merged and passing, the
  implementation branch starts from that exact baseline, documentation
  authority is unambiguous, and runtime behavior remains unchanged.
- **Failure routing:** A stale base, unmerged Phase 2, failed regression, multiple
  migration heads, or runtime diff keeps `P3-01` in `FIXING` or `BLOCKED`;
  `P3-02` remains locked.

### P3-02 — Writing Skill Taxonomy & State Update Policy

- **Purpose:** Freeze the minimal Writing taxonomy and a complete deterministic
  state-update policy before state schemas or implementation depend on it.
- **Dependencies:** `P3-01`.
- **Inputs:** Four persisted Phase 2 criterion bands, existing `BandScore`,
  `writing-core-v1`, product/domain decisions, and rebuildability and
  idempotency invariants from this graph.
- **Deliverables:** A versioned policy specification and boundary/example tests
  defining exactly four skills; taxonomy and state-policy versions;
  initialization; accepted evidence; deterministic evidence order with a stable
  tie-breaker; exact update formula; recency behavior; input/output precision;
  rounding; 0/9 boundaries; duplicate and missing evidence; outliers;
  `evidence_count`; replay/rebuild semantics; and, only if adopted, a
  mathematically defined confidence measure.
- **Required validation:** Review the policy independently of updater code; test
  initialization, single/multiple evidence sequences, ordering ties, boundaries,
  rounding, duplicates, missing evidence, outliers, count semantics, and replay
  examples; prove free-text Phase 2 fields are not canonical state inputs.
- **Acceptance condition:** The taxonomy is exactly `writing-core-v1` with four
  skills, every numeric and ordering decision is explicit and versioned, example
  tests encode the accepted decisions, and `P3-07` has no discretion to invent
  a rule.
- **Failure routing:** Any undecided formula, arbitrary confidence, ambiguous
  order/rounding/count behavior, or failed policy test keeps `P3-02` in
  `FIXING`; `P3-03` and `P3-08` remain locked.

### P3-03 — Learner / Evidence / State Schemas

- **Purpose:** Define strict Pydantic v2 domain and API boundaries for the
  accepted Phase 3 concepts without implementing persistence or algorithms.
- **Dependencies:** `P3-02`.
- **Inputs:** Accepted taxonomy/state policy, existing strict schema patterns and
  `BandScore`, conceptual persistence contract, provenance requirements, and
  planned API responsibilities.
- **Deliverables:** Strict typed schemas for Learner creation/result, Writing
  target, canonical skill key, LearningUpdate, LearningEvidence,
  LearnerSkillState, PracticeRecommendation, state snapshots, reason codes, and
  API responses; safe collection defaults and explicit version fields.
- **Required validation:** Test valid/missing/blank/extra fields; IELTS half-band
  boundaries; target and estimate constraints; canonical skills only; positive
  identifiers/counts/revisions; immutable-value boundaries where appropriate;
  mutable-default safety; complete four-skill state/evidence shapes; and safe
  serialization.
- **Acceptance condition:** Schemas precisely express accepted policy and
  provenance, reuse IELTS band validation, reject partial or unknown canonical
  skills, and contain no ORM, transaction, updater, planner, or LLM behavior.
- **Failure routing:** Schema-policy mismatch, weak validation, mutable defaults,
  or premature implementation keeps `P3-03` in `FIXING`; persistence remains
  locked.

### P3-04 — Persistence Models

- **Purpose:** Represent learners, learning updates, immutable evidence,
  materialized state, and recommendation history with SQLAlchemy 2.x and
  database-level integrity.
- **Dependencies:** `P3-03`.
- **Inputs:** Accepted Phase 3 schemas and policy contracts, existing
  `WritingEvaluation`, SQLAlchemy base/session conventions, and PostgreSQL.
- **Deliverables:** Focused models and relationships for Learner,
  LearningUpdate, LearningEvidence, LearnerSkillState, and
  PracticeRecommendation. Database design must enforce one state row per learner
  and skill, one application/owner per Writing evaluation, canonical skill
  validity, half-band boundaries, positive evidence counts/revisions, nonblank
  policy versions, referential ownership, and auditable snapshots/reason codes.
- **Required validation:** Inspect table metadata, constraints, foreign keys,
  uniqueness, relationships, cascades, server defaults, indexes, JSON/structured
  fields, and SQLAlchemy 2.x style; prove model and schema intent agree; review
  that normal evidence mutation is not exposed as domain behavior.
- **Acceptance condition:** Models encode all required integrity and
  idempotency/ownership invariants in the database rather than relying only on
  Python, while remaining focused on persistence.
- **Failure routing:** Missing database invariants, ambiguous ownership,
  mutable-history design, relationship mismatch, or metadata test failure keeps
  `P3-04` in `FIXING`; migration work remains locked.

### P3-05 — Alembic Migration

- **Purpose:** Add the accepted Phase 3 persistence schema through one
  reproducible and reversible PostgreSQL transition.
- **Dependencies:** `P3-04`.
- **Inputs:** Accepted SQLAlchemy metadata, Phase 2 head `0002_writing`, isolated
  PostgreSQL `test-db`, and repository migration conventions.
- **Deliverables:** Focused Alembic revision(s) for all accepted Phase 3 tables,
  constraints, foreign keys, uniqueness, indexes, upgrade, and downgrade; no
  unrelated Phase 2 schema redesign.
- **Required validation:** Confirm one migration head; run
  `0002_writing -> Phase 3 head -> 0002_writing -> Phase 3 head` against only
  isolated test PostgreSQL; inspect resulting schema and compare it with model
  metadata; prove development data/database is untouched.
- **Acceptance condition:** Phase 2 databases upgrade and reverse without manual
  intervention, model/migration schemas agree, and all database invariants
  survive re-upgrade.
- **Failure routing:** Migration, downgrade, isolation, schema-drift, or
  constraint failure keeps `P3-05` in `FIXING`; extraction and all database
  integration remain locked.

### P3-06 — Writing Evidence Extraction

- **Purpose:** Convert one persisted Phase 2 `WritingEvaluation` into the exact
  canonical evidence input required by the accepted state policy.
- **Dependencies:** `P3-05`.
- **Inputs:** Persisted evaluation criterion bands and provenance, accepted
  taxonomy, Phase 3 evidence schema/model, and Phase 2 model relationships.
- **Deliverables:** Deterministic extraction that produces exactly four
  canonical evidence values with source evaluation identity and relevant
  provider/model/prompt/rubric/scoring/thinking provenance; explicit rejection
  of incomplete or inconsistent persisted source data.
- **Required validation:** Test exact skill-to-column mapping, all four outputs,
  stable ordering, band boundaries, provenance copying, inconsistent/missing
  source failure, no partial output, no free-text-to-skill conversion, no
  provider import/call, and no database mutation by pure extraction logic.
- **Acceptance condition:** The same accepted persisted evaluation always yields
  the same complete four-item evidence set, traceable to its source, with no
  network or LLM dependency.
- **Failure routing:** Partial extraction, unstable mapping, provenance loss,
  free-text authority, invalid source acceptance, or network coupling keeps
  `P3-06` in `FIXING`; state update remains locked.

### P3-07 — Learner State Update Engine

- **Purpose:** Implement the deterministic materialized-state transition and
  rebuild behavior defined by `P3-02`.
- **Dependencies:** `P3-06`.
- **Inputs:** Accepted state policy and examples, canonical ordered evidence,
  strict schemas, and existing materialized state values.
- **Deliverables:** Small deterministic functions for initialization, one-step
  state transition, ordered replay/rebuild, and exact comparison with
  materialized state. The implementation consumes policy constants/version; it
  does not infer rules from data or call an LLM.
- **Required validation:** Run every P3-02 policy example; test sequences,
  ordering ties, boundaries, precision/rounding, duplicate/missing/outlier
  behavior, evidence counts, policy-version mismatch, and deterministic repeated
  runs. Prove
  `replay(accepted evidence history) == materialized learner state` for every
  skill under the same policy.
- **Acceptance condition:** Implementation exactly matches the frozen policy,
  produces reproducible state and counts, and can rebuild all four skill states
  without consulting current state as historical truth.
- **Failure routing:** Policy drift, nondeterminism, replay mismatch, count error,
  or LLM/provider coupling keeps `P3-07` in `FIXING`; planner implementation
  remains locked.

### P3-08 — Practice Planning Policy

- **Purpose:** Freeze a versioned deterministic policy for selecting what
  Writing skill to practice before planner implementation.
- **Dependencies:** `P3-02`.
- **Inputs:** Four canonical skills, learner target band, accepted state-policy
  outputs, product decisions for cold/no/insufficient evidence, and auditability
  requirements.
- **Deliverables:** Planner version and policy specification defining target-gap
  calculation, cold start, no evidence, insufficient evidence, target achieved,
  stable skill priority and explicit tie-breaking, stable reason-code taxonomy,
  decision-time state snapshot requirements, and whether/how an accepted
  deterministic confidence value is used.
- **Required validation:** Table/example tests for all policy branches, target
  boundaries, gap ties, explicit priority ties, absent/insufficient state,
  achieved targets, reason-code stability, input-order independence, and
  serialization of decision evidence.
- **Acceptance condition:** For every valid learner/state input the policy yields
  one unambiguous explainable decision or an explicit defined no-recommendation
  outcome; no implicit order or LLM decision remains.
- **Failure routing:** Undefined cold-start/target-achieved behavior, unstable
  ties, decorative confidence, ambiguous reasons, or failed examples keeps
  `P3-08` in `FIXING`; `P3-09` remains locked even if P3-07 is complete.

### P3-09 — Practice Planner

- **Purpose:** Implement the accepted P3-08 policy as a pure deterministic
  decision component.
- **Dependencies:** `P3-07`, `P3-08`.
- **Inputs:** Valid learner target, complete accepted learner state or defined
  cold-start state, planner policy/version, skill priority, and reason codes.
- **Deliverables:** Structured planner decision containing target skill, current
  estimate when defined, target band, stable reason codes, planner version, and
  the exact decision-time state snapshot; no lesson or exercise content.
- **Required validation:** Execute every P3-08 example; test input-order
  independence, gaps, cold/no/insufficient evidence, ties, target achieved,
  boundaries, reason codes, version propagation, snapshot completeness, and
  repeated-run determinism; assert no LLM/provider dependency.
- **Acceptance condition:** The planner chooses only **what** to practice,
  reproduces the frozen policy exactly, and returns enough structured data to
  persist and explain the decision.
- **Failure routing:** Policy drift, unstable decision, missing audit data,
  lesson generation, or LLM coupling keeps `P3-09` in `FIXING`; application
  orchestration remains locked.

### P3-10 — Learning Update Application Service

- **Purpose:** Orchestrate one atomic, idempotent application of a persisted
  Writing evaluation to a learner.
- **Dependencies:** `P3-05`, `P3-06`, `P3-07`, `P3-09`.
- **Inputs:** SQLAlchemy session, learner and persisted evaluation identities,
  database idempotency/ownership constraints, extractor, updater, planner, and
  accepted policy versions.
- **Deliverables:** Focused application service performing, in one transaction:
  validate learner and source evaluation; claim/create the update anchor; create
  exactly four evidence records; update exactly four skill-state rows; run the
  deterministic planner; persist one recommendation; commit. Same learner plus
  same evaluation returns the existing logical result without duplicate effects;
  a different learner reusing that evaluation returns an explicit conflict.
- **Required validation:** PostgreSQL tests for first apply, same-owner replay,
  cross-owner conflict, exactly four evidence/state records, one recommendation,
  version/provenance retention, deterministic state/planner results, failure at
  each transaction stage, complete rollback of Phase 3 writes, unchanged Phase 2
  evaluation, and no provider call.
- **Acceptance condition:** One successful transaction creates one auditable
  logical update; retries are idempotent, ownership is exclusive, and any failure
  leaves zero partial Phase 3 success.
- **Failure routing:** Duplicate effects, partial writes, ownership ambiguity,
  rollback failure, policy mismatch, or provider coupling keeps `P3-10` in
  `FIXING`; APIs remain locked.

### P3-11 — Learner & Learning APIs

- **Purpose:** Expose minimal learner creation, state inspection, and Writing
  evaluation application through thin FastAPI routes.
- **Dependencies:** `P3-10`.
- **Inputs:** Accepted request/response schemas, application service, learner
  persistence operations, database dependency, and centralized safe error
  mapping conventions.
- **Deliverables:** Equivalent responsibilities to `POST /learners`,
  `GET /learners/{learner_id}/state`, and
  `POST /learners/{learner_id}/writing/evaluations/{evaluation_id}/apply`;
  explicit response schemas and safe not-found/conflict/validation/failure
  responses. Exact paths may follow repository conventions without changing
  responsibilities.
- **Required validation:** API tests for valid/invalid target, learner creation,
  state before/after evidence, successful apply, same-owner idempotent replay,
  cross-owner conflict, learner/evaluation not found, response audit fields,
  rollback behavior, no raw internals, route thinness, and no provider call.
- **Acceptance condition:** HTTP routes delegate all policy and transaction work
  to services, expose stable safe responses, and provide the complete
  deterministic Phase 3 path without unrelated learning workflows.
- **Failure routing:** Route business logic, unsafe error leakage, schema
  mismatch, persistence inconsistency, or provider invocation keeps `P3-11` in
  `FIXING`; concurrency hardening remains locked.

### P3-12 — Concurrency / Failure / Idempotency Hardening

- **Purpose:** Prove and harden database-safe behavior under duplicate and
  concurrent learning updates.
- **Dependencies:** `P3-11`.
- **Inputs:** Application service and API, PostgreSQL constraints and transaction
  semantics, state revision/order policy, stable API errors, and concurrency
  test harness.
- **Deliverables:** Minimal database-safe coordination selected during this node
  (unique constraints, row locks, optimistic revision checks, or equivalent);
  explicit behavior for learner/evaluation missing, cross-owner reuse, database
  conflict, invalid target, and inconsistent persisted source; no process-local
  correctness lock.
- **Required validation:** Against isolated PostgreSQL, execute concurrent same
  learner/same evaluation requests and prove one logical application; execute
  same learner/different evaluations concurrently and prove deterministic,
  uncorrupted final state matching accepted evidence order and replay. Test
  bounded conflict handling, no double counts/evidence/recommendations, atomic
  rollback, stable safe API responses, and unchanged Phase 2 rows.
- **Acceptance condition:** Defined concurrent schedules cannot double apply,
  corrupt state, violate deterministic evidence order, or lose audit history;
  final materialized state equals replayed evidence.
- **Failure routing:** Race, deadlock without bounded handling, double count,
  lost update, replay mismatch, local-lock dependence, or unsafe failure response
  keeps `P3-12` in `FIXING`; consolidated validation remains locked.

### P3-13 — Automated & Integration Validation

- **Purpose:** Consolidate deterministic coverage for the complete Phase 3 path
  while preserving every Phase 1 and Phase 2 gate.
- **Dependencies:** `P3-12`.
- **Inputs:** Policy/example tests, schemas, models/migration, extractor, updater,
  planner, application/API, concurrency cases, isolated PostgreSQL, and existing
  regressions.
- **Deliverables:** Organized unit, API, PostgreSQL constraint, migration,
  transaction, concurrency, replay/rebuild, and end-to-end suites; CI-compatible
  deterministic commands requiring no live DeepSeek key.
- **Required validation:** Cover policy boundaries, evidence extraction, state
  replay, planner decisions, database invariants, idempotency, rollback, API
  failures, same-evaluation concurrency, different-evaluation concurrency, and
  the full flow
  `persisted WritingEvaluation -> apply -> 4 evidence -> 4 state rows -> 1 recommendation`.
  Run complete Phase 1/2/3 regression suites with no required skip and no live
  provider call.
- **Acceptance condition:** All accepted behavior is deterministic and tested
  against isolated PostgreSQL; every Phase 1/2 regression remains passing; CI
  requires no provider credential or network.
- **Failure routing:** Missing required coverage, flaky concurrency, skipped
  required validation, live-network access, or any regression keeps `P3-13` in
  `FIXING`; Docker/documentation remains locked.

### P3-14 — Docker & Documentation

- **Purpose:** Prove clean-checkout reproducibility and synchronize relevant
  documentation with behavior that now exists.
- **Dependencies:** `P3-13`.
- **Inputs:** Complete verified implementation, Dockerfile/Compose topology,
  isolated test database, migrations, API contract, CI commands, and actual
  limitations.
- **Deliverables:** Minimal Docker/Compose changes only if required; clean
  container validation evidence; accurate README, AGENTS, architecture, API, and
  local-development updates; no final audit yet and no unsupported runtime claim.
- **Required validation:** Validate Compose rendering, build runtime/test images,
  run migration and complete containerized suite from a clean checkout, verify
  database isolation and teardown, execute documented commands, resolve links,
  scan images/config/diff for secrets, and compare every documentation claim
  with code/tests.
- **Acceptance condition:** A new developer can reproduce the complete Phase 3
  path with isolated PostgreSQL and no live DeepSeek key, and documentation
  truthfully distinguishes implemented Phase 3 behavior from later work.
- **Failure routing:** Build, migration, container test, isolation, secret, link,
  command, or documentation-truth failure keeps `P3-14` in `FIXING`; final
  audit remains locked.

### P3-15 — Final Phase Audit

- **Purpose:** Decide whether the entire Phase 3 graph satisfies its objective
  and stop boundary.
- **Dependencies:** `P3-14`.
- **Inputs:** All node commits/evidence, complete tests and CI, migration cycle,
  Docker results, provenance/rebuild/idempotency/concurrency evidence,
  documentation, and final repository diff.
- **Deliverables:** `docs/PHASE3_AUDIT.md` created only now, recording completed
  nodes, policy versions, provenance, evidence immutability, rebuildability,
  atomicity, idempotency, deterministic planning, concurrency correctness,
  migrations, CI, Docker, security/scope review, commits, limitations, and next
  phase recommendation.
- **Required validation:** Re-run full local and containerized suites; validate
  one Alembic head and Phase 2/3 downgrade/re-upgrade; execute end-to-end,
  idempotency, cross-owner, rollback, rebuild, planner-explanation, and both
  concurrency scenarios; inspect CI; check links, secrets, forbidden scope,
  documentation truth, and clean Git state.
- **Acceptance condition:** Every `P3-01` through `P3-15` node is
  `COMPLETE`; all success criteria below have evidence; no unauthorized scope
  exists; the audit is truthful; and the graph reaches `STOP`.
- **Failure routing:** Any missing or failed evidence routes to its owning node in
  `FIXING`. `P3-15` and `STOP` remain unavailable until the dependency is
  repaired and all affected validation is rerun.

## Phase 3 success criteria

Phase 3 is complete only when all nodes are `COMPLETE` and evidence proves:

1. a minimal Learner can be created with a validated Writing target;
2. an already persisted Phase 2 `WritingEvaluation` can be applied without a
   provider call;
3. one application creates exactly four immutable canonical evidence records;
4. four learner skill states update deterministically under the accepted policy;
5. one deterministic, auditable recommendation is persisted;
6. the entire Phase 3 write set commits atomically or rolls back;
7. replaying the same learner/evaluation creates no duplicate effect;
8. applying the same evaluation to another learner returns an explicit conflict;
9. rebuilding from ordered evidence reproduces materialized state exactly;
10. stored reason codes and state snapshot explain the historical recommendation;
11. defined concurrent updates do not double count, corrupt state, or lose data;
12. migration upgrade/downgrade/re-upgrade, CI, Docker, and all Phase 1/2
    regressions pass.

## Forbidden Phase 3 scope

Do not add any of the following during Phase 3:

- LangGraph or LangChain
- generic Agent Runtime or Agent Loop
- multi-agent architecture
- RAG, pgvector, vector memory, or semantic retrieval
- Redis, Celery, Kafka, or another background-task system
- Speaking, Reading, or Listening
- frontend
- automatic lesson or exercise generation
- LLM-based state updates or practice planning
- complex skill ontology or skill graph
- reinforcement learning
- fine-tuning

Do not add these for speculative future extensibility. Phase 3 remains one
application using PostgreSQL and deterministic domain/services.

## Execution and stop rule

For each explicitly authorized selected node, follow
[DEVELOPMENT_LOOP.md](DEVELOPMENT_LOOP.md):

```text
Observe -> Select -> Plan -> Implement -> Test -> Review -> Fix -> Commit -> Repeat
```

This graph does not authorize automatic continuous execution. Do not activate
`P3-01` without a separate implementation instruction. Never bypass a failed
gate or start a node whose dependencies are incomplete. After `P3-15` is
`COMPLETE`, **STOP**. Do not begin Phase 4 automatically.
