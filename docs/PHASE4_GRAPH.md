# Phase 4 Graph — Adaptive Writing Practice Loop

## Document status

**DESIGN ONLY — NOT EXECUTION AUTHORIZED.**

This document defines the Phase 4 execution graph. It does NOT authorize any
runtime implementation. After this Graph passes external review, a separate
explicit user authorization is required to activate `P4-01`. No Phase 4 node
is `ACTIVE` and no Phase 4 runtime code exists.

Accepted baseline: `master` @ `8cb0b73` (`feat: complete Phase 3 learner state
and adaptive planning (#7)`), with Phase 3 merged and master CI green. Current
single Alembic head: `0003_learning`.

---

## 1. Phase 4 goal

Phase 4 extends the implemented Phase 3 path

```text
WritingEvaluation -> LearningEvidence -> LearnerState -> PracticeRecommendation
```

into a closed adaptive Writing practice loop:

```text
PracticeRecommendation
  -> Targeted Writing Practice (generated)
  -> Learner Submission
  -> WritingEvaluation (existing Phase 2)
  -> LearnerState Update (existing Phase 3 apply)
  -> New PracticeRecommendation
```

The target learning loop is:

```text
Observe -> Plan -> Practice -> Evaluate -> Update -> Replan
```

## 2. Product boundary

**Central invariant:**

- Phase 3 decides **WHAT** the learner should practice (`target_skill`,
  `reason`, learner target, planner version).
- Phase 4 may use an LLM to decide **HOW** to instantiate that practice: an
  IELTS Writing Task 2 question, a focused practice objective, and a small set
  of targeted instructions/checkpoints, plus metadata proving which
  recommendation produced the practice.

The generator MUST NOT override `target_skill`, learner target, planner
reason, learner state, or planner version. LLM output is generated content,
never learner-state authority. No Phase 4 model call may directly mutate
`LearnerSkillState`.

## 3. Scope

### 3.1 In scope

- Targeted Writing Task 2 practice generation.
- Versioned practice-generation policy (`writing-practice-generation-v1`).
- Structured practice schemas, practice persistence, learner ownership, and
  association with the originating `PracticeRecommendation`.
- Practice submission tracking integrated with the existing Writing evaluation
  pipeline and the existing Phase 3 learning apply.
- Closed-loop replan result exposure (the next `PracticeRecommendation`).
- DeepSeek practice generator plus a deterministic Fake generator for tests.
- Safe generation failures, idempotency, PostgreSQL concurrency correctness,
  REST APIs, Docker/test/documentation work.

### 3.2 Non-goals (forbidden Phase 4 scope)

- LangGraph / LangChain / generic Agent Runtime / generic Loop Runtime /
  multi-agent architecture.
- RAG, pgvector, vector memory, semantic retrieval.
- Redis, Celery, Kafka, background-job frameworks.
- Speaking, Reading, Listening.
- Frontend / Next.js.
- Long-term learning memory, reflection engine, memory retrieval.
- Fine-tuning, RL, complex ontology, complex skill graph.
- Automatic multi-week curriculum, full course generation, unbounded lesson
  generation.
- Redesigning Phase 2 scoring.
- Redesigning Phase 3 state/planner policies.

Phase 4 remains FastAPI + SQLAlchemy + PostgreSQL + deterministic domain
logic + one small provider adapter for practice generation.

## 4. Authority hierarchy

1. `AGENTS.md`
2. `docs/PHASE4_GRAPH.md` (this document)
3. Accepted frozen policies: `docs/WRITING_STATE_POLICY.md`,
   `docs/PRACTICE_PLANNING_POLICY.md`, and the Phase 4 generation policy
   frozen by `P4-03` (`docs/WRITING_PRACTICE_GENERATION_POLICY.md`).
4. Accepted schemas/models (Phase 2/3 frozen contracts + Phase 4 frozen
   schemas).
5. `docs/DEVELOPMENT_LOOP.md`
6. Current implementation/tests.

Phase 2 remains authority for Writing Task 2 evaluation, the provider
boundary, validated structured evaluation, `WritingAttempt`, and
`WritingEvaluation`. Phase 3 remains authority for `LearningEvidence`,
`LearnerSkillState`, `PracticeRecommendation`, `writing-core-v1`,
`writing-state-ewma-v1`, and `writing-practice-gap-v1`. Phase 4 consumes
`PracticeRecommendation`; it never recalculates what skill to practice with
another LLM prompt.

## 5. Accepted invariants (must not be broken)

- Phase 2 evaluation and provider boundary unchanged.
- Phase 3 state/planner policies unchanged (`writing-state-ewma-v1`,
  `writing-practice-gap-v1`, taxonomy `writing-core-v1`).
- `PracticeRecommendation` controls WHAT; generator controls HOW.
- No provider/network call inside a database transaction.
- A persisted evaluation remains reusable without calling the LLM again.
- One logical practice per originating recommendation (deterministic
  idempotency, see section 8).
- Auditability: the practice history must answer which recommendation created
  which practice, which learner received it, whether it was submitted, which
  attempt/evaluation/update resulted, and what the next recommendation was.

## 6. Conceptual closed-loop flow

```text
PracticeRecommendation (Phase 3)
        |
        v
PracticeTask (generated Writing practice; one durable concept, see 7)
        |
        v
PracticeSession (lightweight association = the practice row + status;
                 not a separate table, see 7)
        |
        v
Learner submits essay -> WritingAttempt (Phase 2)
        |
        v
WritingEvaluation (Phase 2, provider outside transaction)
        |
        v
LearningUpdate (existing Phase 3 apply; 4 evidence + 4 states + 1 decision)
        |
        v
next PracticeRecommendation (exposed as closed-loop result)
```

## 7. Persistence design decision

Do NOT blindly create separate tables for `PracticeTask` and
`PracticeSession`. The minimum durable model that provides auditability,
idempotency, ownership, and closed-loop traceability is **one table**:

`writing_practices`

- `id` PK.
- `learner_id` FK -> `learners` (RESTRICT); ownership anchor.
- `recommendation_id` FK -> `practice_recommendations` (RESTRICT), with a
  global `UNIQUE (recommendation_id)` idempotency anchor: one originating
  recommendation yields exactly one practice.
- `target_skill` (authoritative copy of the recommendation's target), and
  generator-policy version.
- Generated content: `question`, `focus_objective`, `instructions` (JSONB),
  `checkpoints` (JSONB), `practice_type`.
- Provenance: `provider`, `model`, `prompt_version`, `thinking_mode`,
  generation status / error category (safe only).
- Submission link: `attempt_id` FK -> `writing_attempts` (SET NULL / NULL
  until submitted; a completed submission references exactly one attempt).
- `created_at`, `updated_at`.

Closed-loop traceability is then a query path, not extra tables:
`practice.recommendation_id` -> originating decision;
`practice.attempt_id` -> `WritingAttempt` -> `WritingEvaluation`
(evaluation.attempt_id) -> `LearningUpdate` (by writing_evaluation_id) ->
`PracticeRecommendation` (by learning_update_id) = next decision.

`PracticeSession` is a derived association (the practice row plus its status),
not a durable table. Status values are frozen by `P4-02` (e.g. `generated`,
`submitted`, and any completion semantics the product contract requires).

## 8. Idempotency semantics (frozen answers)

- **Retry "generate next practice" for the same originating recommendation →
  the SAME practice** (deterministic product semantics; duplicate generation
  is accidental and prevented by `UNIQUE (recommendation_id)` plus an
  under-lock re-check).
- Same practice submission retry -> returns the existing `WritingAttempt` /
  evaluation result; no duplicate submission effects.
- Same evaluation apply retry -> existing Phase 3 idempotency (unchanged).
- Practice ownership: a practice belongs to exactly one learner; applying it
  to another learner is an explicit conflict.
- Cross-learner reuse of an originating recommendation is impossible by
  construction (recommendation already learner-owned via Phase 3).
- Concurrency: per-learner row locking plus the unique anchors, mirroring the
  accepted Phase 3 approach; no process-local correctness locks.

## 9. Generator contract boundary

Free-form model text never becomes the database contract. The generation
policy (`P4-03`) freezes a structured boundary before implementation:

- Input authority: the accepted `PracticeRecommendation` (target skill,
  learner target, reason codes, planner version, snapshot) — read-only.
- Structured output: `GeneratedWritingPractice` with `practice_type`,
  `target_skill`, `question`, `focus_objective`, `instructions`, `checkpoints`,
  and generator policy version + provider/model/prompt/thinking provenance.
- Prompt ownership: application-owned prompt templates with a frozen
  `prompt_version`; the policy defines supported skills, Task 2 scope, content
  constraints, maximum sizes, safety constraints, fallback behavior, retry
  classes, idempotency, and provenance requirements.

## 10. LLM architecture decision

The existing Phase 2 `LLMProvider` protocol is Writing-evaluator-specific
(`evaluate_writing`); do not bend it into a generation gateway. Add the
smallest focused abstraction:

```text
PracticeGenerator (Protocol, async)
  generate_practice(request: PracticeGenerationRequest) -> GeneratedWritingPractice
```

- Reuses the accepted `ProviderError` / `ProviderErrorCategory` /
  `ProviderRetryPolicy` / `RetryingProvider` failure normalization and the
  DeepSeek `httpx.AsyncClient` injection pattern.
- `DeepSeekPracticeGenerator` implements the protocol using application-owned
  prompt templates.
- `FakePracticeGenerator` provides deterministic generated practices for
  tests and CI (no live key, no network).
- No second generic model gateway, no Agent framework, no Tool framework.

## 11. Provider/network rules

- All provider/network calls happen OUTSIDE database transactions.
- Boundaries: generate -> persist practice (two phases); submit -> existing
  Phase 2 evaluation (provider outside transaction); apply persisted
  evaluation -> existing Phase 3 service; then expose the new recommendation.
- A persisted evaluation is reusable without re-invoking the LLM.
- No live DeepSeek key is required for any Phase 4 test or CI run.

## 12. Test strategy

Required coverage:

- pure generation-policy tests (frozen branches, constraints, provenance);
- schema tests;
- generator-contract tests and Fake-generator determinism;
- provider adapter tests without live network (injected client);
- real PostgreSQL persistence tests (ownership, unique anchors, FKs);
- migration upgrade/downgrade/re-upgrade + drift + single head;
- idempotency, ownership, cross-learner conflict, rollback;
- safe API failure tests (no raw leakage; stable error contract);
- concurrency tests where shared mutable state exists (same recommendation
  generate race; same practice submit race);
- full Phase 1/2/3/4 regression, no required skip, no live model;
- Docker clean-checkout validation; PR CI with no DeepSeek credentials.

The final closed-loop integration test must demonstrate, without a live model:

```text
Recommendation -> Practice -> Submission -> Evaluation -> Learning Apply
-> New State -> New Recommendation
```

using the Fake generator and the existing Fake/isolated evaluation path.

## 13. Node state model

`NOT_STARTED` / `READY` / `ACTIVE` / `COMPLETE` / `FIXING`, mirroring Phase 3.
All nodes are currently `NOT_STARTED`; nothing is authorized to run until a
separate explicit execution authorization activates `P4-01`.

## 14. Dependency graph

```text
P4-01 Phase 4 Baseline & Transition
  -> P4-02

P4-02 Adaptive Writing Practice Product Contract
  -> P4-03
  -> P4-10 (submission / closed-loop semantics)

P4-03 Writing Practice Generation Policy
  -> P4-04
  -> P4-07

P4-04 Practice Domain / API Schemas
  -> P4-05

P4-05 Practice Persistence Models
  -> P4-06

P4-07 Practice Generator Contract
  -> P4-08

P4-06 + P4-04 + P4-07 -> P4-09

P4-09 + P4-02 -> P4-10

P4-10 -> P4-11

P4-11 -> P4-12

P4-12 -> P4-13

P4-13 -> P4-14

P4-14 -> P4-15

P4-15 -> P4-16

P4-16 -> STOP
```

P4-03 -> P4-04 and P4-03 -> P4-07 both follow from the generation policy
being the single authority for both schema shape and generator contract.
P4-02 -> P4-10 is added because submission and closed-loop semantics are
product-contract decisions, not implementation details.

---

## 15. Node definitions

### P4-01 — Phase 4 Baseline & Transition

- **Type:** design / documentation
- **Purpose:** Verify the accepted Phase 3 baseline and open Phase 4.
- **Dependencies:** none (requires explicit execution authorization).
- **Inputs / authority:** accepted `master` @ `8cb0b73`; Phase 3 merged; CI
  green; `docs/PHASE3_AUDIT.md`.
- **Deliverables:** baseline evidence: master SHA, single Alembic head
  `0003_learning`, Phase 1/2/3 tests pass, no Phase 4 runtime present, clean
  branch; transition record in this Graph.
- **Acceptance criteria:** all baseline checks recorded truthfully.
- **Forbidden scope:** any runtime implementation.
- **Failure / FIXING:** stale baseline, extra Alembic head, or existing Phase 4
  code keeps `P4-01` in `FIXING`.
- **Unlocks:** `P4-02`.

### P4-02 — Adaptive Writing Practice Product Contract

- **Type:** design / policy
- **Purpose:** Freeze exactly what Phase 4 means by Practice, Practice Session,
  Submission, completion, and closed-loop result; smallest useful user story.
- **Dependencies:** `P4-01`.
- **Inputs / authority:** Phase 3 recommendation contract; Phase 2 evaluation
  pipeline.
- **Deliverables:** accepted definitions and status vocabulary; the primary
  end-to-end acceptance story: learner target 7.0 with TR 6.0 / CC 6.5 / LR
  6.5 / GRA 6.5 -> Phase 3 recommends `task_response` -> Phase 4 generates one
  Task-Response-focused Task 2 practice -> learner submits -> Phase 2
  evaluates -> Phase 3 applies -> new state -> new recommendation.
- **Acceptance criteria:** the story is unambiguous, testable end-to-end with
  fakes, and all Phase 4 API behavior traces to it.
- **Forbidden scope:** lesson generation, curriculum, other skills.
- **Failure / FIXING:** ambiguous session/completion semantics keep `P4-02` in
  `FIXING`.
- **Unlocks:** `P4-03`, `P4-10`.

### P4-03 — Writing Practice Generation Policy

- **Type:** design / policy
- **Purpose:** Freeze `writing-practice-generation-v1` BEFORE any generator
  implementation.
- **Dependencies:** `P4-02`.
- **Inputs / authority:** accepted recommendation contract.
- **Deliverables:** `docs/WRITING_PRACTICE_GENERATION_POLICY.md` defining input
  authority, supported target skills, Task 2 scope, structured output
  requirements, prompt ownership + version, provider provenance, retry
  classes, content limits, safety constraints, idempotency behavior, failure
  semantics. Explicit: no LLM chooses `target_skill`.
- **Acceptance criteria:** every frozen rule is testable; the policy states
  "Recommendation controls WHAT; generator controls HOW."
- **Forbidden scope:** state/planner override, multi-skill content.
- **Failure / FIXING:** free-form contract, missing limits, or state-authority
  ambiguity keeps `P4-03` in `FIXING`.
- **Unlocks:** `P4-04`, `P4-07`.

### P4-04 — Practice Domain / API Schemas

- **Type:** schema
- **Purpose:** Freeze strict Pydantic v2 schemas for generated practice,
  submission, and API boundaries (mirroring Phase 2/3 schema discipline).
- **Dependencies:** `P4-03`.
- **Inputs / authority:** generation policy; `P4-02` product contract.
- **Deliverables:** schemas for `GeneratedWritingPractice`, submission
  association, practice response, closed-loop result, and safe error mapping
  additions only if required.
- **Acceptance criteria:** schema tests pass; no ORM/service/LLM behavior in
  schemas.
- **Forbidden scope:** planner/state schema redesign.
- **Failure / FIXING:** mutable defaults, missing constraints, or leakage of
  provider internals keeps `P4-04` in `FIXING`.
- **Unlocks:** `P4-05`.

### P4-05 — Practice Persistence Models

- **Type:** database
- **Purpose:** Implement the minimal `writing_practices` model (section 7).
- **Dependencies:** `P4-04`.
- **Inputs / authority:** frozen schemas; Phase 3 model conventions.
- **Deliverables:** SQLAlchemy 2.x model with FKs, ownership anchors,
  `UNIQUE (recommendation_id)`, timestamps, provenance columns, RESTRICT/SET
  NULL deletion semantics.
- **Acceptance criteria:** model tests (constraints, anchors, ownership) pass;
  no business logic in models.
- **Forbidden scope:** memory/events tables, curriculum tables.
- **Failure / FIXING:** broken anchors, missing ownership, or generic-history
  design keeps `P4-05` in `FIXING`.
- **Unlocks:** `P4-06`.

### P4-06 — Alembic Migration

- **Type:** database
- **Purpose:** Add reversible migration `0004_writing_practice` (single head).
- **Dependencies:** `P4-05`.
- **Inputs / authority:** accepted model.
- **Deliverables:** upgrade/downgrade/re-upgrade verified on real PostgreSQL;
  drift check; constraint tests.
- **Acceptance criteria:** linear history `0001 -> 0002 -> 0003 -> 0004`,
  single head, downgrade removes only Phase 4 tables.
- **Forbidden scope:** schema changes to Phase 2/3 tables.
- **Failure / FIXING:** drift, non-reversible downgrade, or head conflicts
  keep `P4-06` in `FIXING`.
- **Unlocks:** `P4-09`, `P4-10`.

### P4-07 — Practice Generator Contract

- **Type:** domain logic (interface)
- **Purpose:** Freeze the `PracticeGenerator` protocol and request/response
  types from `P4-03`.
- **Dependencies:** `P4-03`.
- **Inputs / authority:** generation policy.
- **Deliverables:** protocol with `generate_practice`, typed request (authority
  values only) and `GeneratedWritingPractice` response; failure normalization
  reusing `ProviderError`.
- **Acceptance criteria:** contract tests with a stub pass; no state mutation.
- **Forbidden scope:** generic gateway/tool abstractions.
- **Failure / FIXING:** contract leakage, untyped output, or state write
  attempts keep `P4-07` in `FIXING`.
- **Unlocks:** `P4-08`.

### P4-08 — DeepSeek Practice Generator + deterministic test fake

- **Type:** provider
- **Purpose:** Implement the production generator and the deterministic fake.
- **Dependencies:** `P4-07`.
- **Inputs / authority:** `P4-03` policy; `P4-07` contract.
- **Deliverables:** `DeepSeekPracticeGenerator` (reusing the accepted httpx
  injection and `ProviderError`/retry patterns) and `FakePracticeGenerator`
  (deterministic, policy-valid content).
- **Acceptance criteria:** adapter tests with injected client (no live
  network); fake determinism tests; provenance recorded.
- **Forbidden scope:** network in tests; target-skill authority.
- **Failure / FIXING:** live-network test coupling or contract drift keeps
  `P4-08` in `FIXING`.
- **Unlocks:** `P4-09`.

### P4-09 — Practice Generation Service

- **Type:** application service
- **Purpose:** Orchestrate one atomic, idempotent practice generation.
- **Dependencies:** `P4-06`, `P4-04`, `P4-07`.
- **Inputs / authority:** persisted recommendation, learner, generator,
  session, unique anchor.
- **Deliverables:** service that validates recommendation ownership, runs the
  generator OUTSIDE the transaction, persists one `writing_practices` row,
  and returns the same practice on retry (idempotent); rollback on persistence
  failure; safe generator-failure mapping.
- **Acceptance criteria:** PostgreSQL tests for first generate, idempotent
  retry, cross-learner conflict, rollback, provider failure (no row), and
  provenance retention.
- **Forbidden scope:** LLM inside transaction; state mutation.
- **Failure / FIXING:** duplicate practices, partial writes, or provider
  coupling keeps `P4-09` in `FIXING`.
- **Unlocks:** `P4-10`.

### P4-10 — Practice Session / Submission Integration

- **Type:** application service
- **Purpose:** Bind a generated practice to a learner submission and the
  existing Phase 2 evaluation.
- **Dependencies:** `P4-09`, `P4-02`.
- **Inputs / authority:** practice identity, submission, Phase 2 evaluation
  pipeline.
- **Deliverables:** submission association (practice -> `WritingAttempt` ->
  `WritingEvaluation`) with idempotent resubmission and unchanged Phase 2
  semantics.
- **Acceptance criteria:** real-PostgreSQL tests for first submit, resubmit
  idempotency, ownership, and closed-loop link integrity.
- **Forbidden scope:** bypassing Phase 2 evaluation; new scoring.
- **Failure / FIXING:** broken attempt link, duplicate submission, or Phase 2
  bypass keeps `P4-10` in `FIXING`.
- **Unlocks:** `P4-11`.

### P4-11 — Closed-loop Application Service

- **Type:** application service
- **Purpose:** Compose generate -> submit -> Phase 3 apply -> expose the next
  recommendation, keeping every provider call outside transactions.
- **Dependencies:** `P4-10`.
- **Inputs / authority:** practice, evaluation, existing Phase 3 apply.
- **Deliverables:** deterministic closed-loop orchestration returning the
  persisted next `PracticeRecommendation`; retryable boundaries.
- **Acceptance criteria:** full closed-loop PostgreSQL test with fakes (no
  live model); exactly one practice per recommendation; exactly one next
  recommendation.
- **Forbidden scope:** giant single-transaction endpoint with provider calls.
- **Failure / FIXING:** transaction/provider mixing or missing replan result
  keeps `P4-11` in `FIXING`.
- **Unlocks:** `P4-12`.

### P4-12 — Practice APIs

- **Type:** API
- **Purpose:** Thin routes for generating/inspecting practice, submitting work,
  and observing the closed-loop result.
- **Dependencies:** `P4-11`.
- **Inputs / authority:** frozen schemas, services, existing error contract.
- **Deliverables:** safe endpoints (exact paths frozen here) exposing the
  auditable planning decision and closed-loop result; no raw internals.
- **Acceptance criteria:** API tests for generate/idempotent retry/inspect/
  submit/closed-loop/safe 4xx/5xx; no provider call in tests.
- **Forbidden scope:** frontend-specific APIs; business logic in routes.
- **Failure / FIXING:** route business logic, unsafe leakage, or missing
  closed-loop fields keeps `P4-12` in `FIXING`.
- **Unlocks:** `P4-13`.

### P4-13 — Idempotency / Failure / Concurrency Hardening

- **Type:** test / hardening
- **Purpose:** Prove database-safe behavior for duplicate and concurrent
  practice generation/submission against real PostgreSQL.
- **Dependencies:** `P4-12`.
- **Inputs / authority:** services, APIs, unique anchors, per-learner row
  locks.
- **Deliverables:** controlled concurrency tests (same recommendation race ->
  one practice; same practice submit race -> one attempt link) using the
  PostgreSQL wait-state observation pattern accepted in Phase 3; bounded
  conflict handling.
- **Acceptance criteria:** no duplicate practices/attempts/decisions; final
  state deterministic; no local-lock correctness.
- **Forbidden scope:** changing generation/state policy to pass tests.
- **Failure / FIXING:** race, double effect, or replay mismatch keeps `P4-13`
  in `FIXING`.
- **Unlocks:** `P4-14`.

### P4-14 — Closed-loop Integration Validation

- **Type:** test
- **Purpose:** Consolidate the complete deterministic Phase 4 path.
- **Dependencies:** `P4-13`.
- **Inputs / authority:** all Phase 1/2/3/4 suites.
- **Deliverables:** organized unit/API/PostgreSQL/concurrency/end-to-end
  coverage for the full loop with fakes; full regression, no required skip,
  no live provider.
- **Acceptance criteria:** the closed-loop acceptance story passes end-to-end;
  every Phase 1/2/3 regression remains green.
- **Forbidden scope:** live-network tests; weakening existing tests.
- **Failure / FIXING:** missing required coverage or regressions keep `P4-14`
  in `FIXING`.
- **Unlocks:** `P4-15`.

### P4-15 — Docker / Documentation / Reproducibility

- **Type:** documentation / validation
- **Purpose:** Prove clean-checkout reproducibility and synchronize truthful
  documentation.
- **Dependencies:** `P4-14`.
- **Inputs / authority:** verified implementation, Compose topology, migration,
  API contract.
- **Deliverables:** containerized full-suite validation; README/AGENTS/
  ARCHITECTURE/API/local-dev updates only as required; no final audit yet.
- **Acceptance criteria:** clean-checkout containerized tests pass; docs match
  implemented behavior and separate Phase 4 from future phases.
- **Forbidden scope:** documenting features that do not exist.
- **Failure / FIXING:** doc drift or container failure keeps `P4-15` in
  `FIXING`.
- **Unlocks:** `P4-16`.

### P4-16 — Final Phase Audit

- **Type:** documentation
- **Purpose:** Audit the entire Phase 4 and declare completion.
- **Dependencies:** `P4-15`.
- **Inputs / authority:** node statuses, policies, commits, PostgreSQL/API/
  Docker/CI evidence.
- **Deliverables:** `docs/PHASE4_AUDIT.md` with node status, policy versions,
  commit checkpoints, closed-loop proof (recommendation -> practice ->
  submission -> evaluation -> apply -> new state -> new recommendation),
  idempotency/ownership/concurrency results, migration head, security/scope
  review, known limitations, and next-phase recommendation.
- **Acceptance criteria:** only if all Phase 4 acceptance criteria pass is
  `P4-16` COMPLETE and Phase 4 STOP.
- **Forbidden scope:** claiming approval that has not occurred.
- **Failure / FIXING:** missing evidence or unrun required validation keeps
  `P4-16` in `FIXING`.
- **Unlocks:** STOP (Phase 5 remains NOT_STARTED).

---

## 16. Database safety

- All destructive/integration work uses the isolated test database guarded by
  `validate_test_database_url` (test token + never the development DB).
- No `.env` committed; no secrets; environment-based configuration only.
- Downgrade/truncate only on verified test-only databases.
- Migration contract: linear history `0001_phase1 -> 0002_writing ->
  0003_learning -> 0004_writing_practice`, single head, reversible, zero drift.

## 17. Git rules

- Work on `phase/4-adaptive-writing-practice` (from accepted `master`).
- Never push directly to `master`.
- One node = one focused checkpoint commit (additive; no history rewriting).
- Suggested checkpoint naming follows Phase 3 conventions (e.g. `feat:`,
  `fix:`, `test:`, `docs:` prefixes).
- After the Graph is accepted and execution is separately authorized, each
  completed node is committed, pushed, and the Graph status updated before the
  next READY node activates.

## 18. STOP conditions

- Required work falls outside Phase 4 scope.
- An unresolved architectural decision is not already frozen by this Graph or
  the accepted policies.
- Required isolated PostgreSQL cannot be safely accessed.
- Continuing would risk a development/production database.
- A required external dependency is unavailable and cannot be replaced by the
  accepted Fake approach.
- A security or secret exposure issue is discovered.
- A node would require forbidden Phase 4 scope.
- Repository state contains unexplained conflicting user changes.

Normal implementation bugs are not STOP conditions; fix them automatically.

## 19. Execution authority

This Graph does NOT authorize runtime execution. After external review of this
Graph, a separate explicit user authorization is required to activate `P4-01`.
No continuous execution begins automatically.

## 20. Final acceptance criteria (Phase 4)

- The closed loop `Recommendation -> Practice -> Submission -> Evaluation ->
  Apply -> New State -> New Recommendation` is implemented and proven with
  fakes on isolated PostgreSQL.
- Exactly one practice per originating recommendation; exactly one
  recommendation per successful apply; idempotent retries; explicit ownership
  conflicts.
- Provider calls stay outside transactions; a persisted evaluation is reusable
  without re-invoking the LLM.
- All Phase 1/2/3 regressions remain green; full suite passes with no required
  skip and no live DeepSeek key; Docker clean-checkout validation passes.
- Single Alembic head; no forbidden scope; no secrets; truthful documentation.

## 21. Phase 5 boundary

Phase 5 (not designed here) would introduce long-term learning memory,
reflection, and possibly additional skills. Phase 4 deliberately builds
transactional practice history only — not a generic memory or events system.

---

**Design status:** GRAPH READY FOR EXTERNAL REVIEW — no runtime execution
authorized. All `P4-01` … `P4-16` nodes are `NOT_STARTED`. Phase 5 remains
`NOT_STARTED`.
