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
  `reason`, learner target, planner version, decision type).
- Phase 4 may use an LLM to decide **HOW** to instantiate a **practice**
  decision: an IELTS Writing Task 2 question, a focused practice objective,
  and a small set of targeted instructions/checkpoints, plus metadata proving
  which recommendation produced the practice.

The generator MUST NOT override `target_skill`, learner target, planner
reason, learner state, planner version, or decision type. LLM output is
generated content, never learner-state authority. No Phase 4 model call may
directly mutate `LearnerSkillState`.

## 3. Scope

### 3.1 In scope

- Targeted Writing Task 2 practice generation **for `practice` decisions
  only**.
- Versioned practice-generation policy (`writing-practice-generation-v1`).
- Structured practice schemas, practice persistence, learner ownership, and
  association with the originating `PracticeRecommendation`.
- A frozen submission-claim protocol integrating with the existing Writing
  evaluation pipeline and the existing Phase 3 learning apply.
- Closed-loop completion / replan result exposure (the next
  `PracticeRecommendation`).
- DeepSeek practice generator plus a deterministic Fake generator for tests.
- Safe generation and submission failures, idempotency, PostgreSQL
  concurrency correctness, REST APIs, Docker/test/documentation work.

### 3.2 Non-goals (forbidden Phase 4 scope)

- LangGraph / LangChain / generic Agent Runtime / generic Loop Runtime /
  multi-agent architecture.
- RAG, pgvector, vector memory, semantic retrieval.
- Redis, Celery, Kafka, background-job frameworks, distributed job
  infrastructure, leases/queues.
- Speaking, Reading, Listening.
- Frontend / Next.js.
- Long-term learning memory, reflection engine, memory retrieval.
- Fine-tuning, RL, complex ontology, complex skill graph.
- Automatic multi-week curriculum, full course generation, unbounded lesson
  generation.
- Bootstrap/diagnostic practice generation for cold-start learners.
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

- Phase 2 evaluation and provider boundary unchanged (scoring, rubric,
  evaluation semantics untouched).
- Phase 3 state/planner policies unchanged (`writing-state-ewma-v1`,
  `writing-practice-gap-v1`, taxonomy `writing-core-v1`).
- `PracticeRecommendation` controls WHAT; generator controls HOW.
- **Decision-gated practice:** only `decision_type = practice` may produce a
  durable `writing_practices` row; `decision_type = no_practice` MUST produce
  zero rows, zero generator calls, and a deterministic no-practice outcome.
- **Cold-start boundary:** a learner with `cold_start` (no eligible Phase 3
  recommendation) receives NO Phase 4 practice; they obtain Writing evidence
  through the existing submission/evaluation path first.
- No provider/network call inside a database transaction.
- A persisted evaluation remains reusable without calling the LLM again.
- Phase 3 apply idempotency remains the authority for learner-state updates;
  Phase 4 never implements a second update mechanism.
- Generation is SUCCESS-ONLY persistence: a durable `writing_practices` row
  exists only for a successfully generated practice.
- **Database-enforced ownership:** `writing_practices(recommendation_id,
  learner_id)` must reference `practice_recommendations(id, learner_id)`
  through a composite foreign key (RESTRICT). The database, not only the
  service, guarantees a recommendation belongs to the same learner as the
  practice. This requires one narrow additive candidate key
  `UNIQUE(id, learner_id)` on `practice_recommendations` (section 12).
- **Practice owns the question:** the generated IELTS Task 2 question is
  authoritative; a Phase 4 submission is essay-only and can never replace the
  practice question (section 12a).
- Auditability: the practice history must answer which recommendation created
  which practice, which learner received it, whether it was submitted, which
  attempt/evaluation/update resulted, and what the next recommendation was.

## 6. Decision semantics (no_practice / cold_start)

Phase 3 produces two decision classes, and Phase 4 treats them asymmetrically:

- **`practice`** — `target_skill` is authoritative; Phase 4 MAY generate
  exactly one targeted Writing practice (at most one durable row; see 8).
- **`no_practice`** — Phase 4 MUST:
  - NOT call the PracticeGenerator;
  - NOT create a `writing_practices` row;
  - NOT invent a `target_skill`;
  - NOT ask an LLM what should be practiced;
  - return/expose a deterministic no-practice outcome based on the persisted
    Phase 3 recommendation (reason codes `cold_start`, `incomplete_state`,
    `target_achieved`, `target_unset` remain Phase 3-owned and are never
    reinterpreted).

**Frozen Phase 4 v1 decision — cold start:** Phase 4 does NOT implement
bootstrap/diagnostic practice generation. A cold-start learner must obtain
Writing evidence through the already-existing Writing submission/evaluation
path before adaptive targeted practice is available. Therefore
`cold_start -> no targeted Phase 4 practice -> no generator call -> no
writing_practices row`. Bootstrap/onboarding practice generation is
explicitly OUT OF SCOPE. Do NOT invent a generic starter lesson.

## 7. Conceptual closed-loop flow

```text
PracticeRecommendation (Phase 3; decision_type = practice only)
        |
        v
Targeted Writing Practice (generated; one durable writing_practices row)
        |
        |   HUMAN PRACTICE TIME (minutes/hours/days)
        v
Learner submits essay -> Submission Claim -> WritingAttempt (Phase 2)
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

## 8. Generation idempotency (frozen semantics)

**SUCCESS-ONLY practice persistence.** A `writing_practices` row is NEVER
persisted before the generator succeeds, and a failed generation leaves no
row (no durable failed-generation state; no error-category column).

```text
load + validate recommendation (learner ownership, decision_type = practice)
if existing practice for recommendation: return it
if no_practice: return deterministic no-practice outcome
call generator OUTSIDE DB transaction
validate structured generated output (target_skill must equal the
  recommendation's target_skill; mismatch = invalid provider response)
short persistence transaction
  insert writing_practices  (UNIQUE(recommendation_id) decides the winner)
commit
```

**Concurrency truth (v1):** concurrent first-generation requests for the same
recommendation MAY both temporarily invoke the provider. Phase 4 v1
guarantees: at most one durable `writing_practices` row per recommendation;
`UNIQUE(recommendation_id)` decides the winner; the losing request resolves
the already-persisted winner and returns that same durable practice; no
duplicate durable practice survives. **Exactly-once provider invocation is NOT
guaranteed and is a documented v1 limitation.** Network side effects are
at-least-once within a bounded retry policy.

The database uniqueness anchor prevents multiple durable practices; it does
NOT authorize generation for `no_practice` decisions — service/application
validation must verify eligibility BEFORE any model call.

## 9. Practice lifecycle (frozen semantics)

The durable practice exists only after generation succeeds. The lifecycle is
around SUBMISSION, not generation:

```text
generated -> submission_in_progress -> submitted
```

- `generated`: row exists, no claim, `attempt_id` NULL.
- `submission_in_progress`: a claim is active (claim token + fingerprint),
  evaluator may run; a second claim request returns a safe in-progress
  outcome.
- `submitted`: `WritingAttempt` + `WritingEvaluation` + `attempt_id` link are
  atomically finalized; the practice cannot be re-submitted with a different
  essay.

Do NOT add a redundant `completed` field to mirror Phase 3. Closed-loop
completion is DERIVED from the trace `practice -> attempt -> evaluation ->
LearningUpdate -> next PracticeRecommendation` (see 13). Exact enum/schema
names are frozen by P4-02/P4-04; the semantics above are fixed now.

## 10. Submission claim protocol (frozen)

The Phase 2 route is NOT idempotent for repeated submissions: each successful
invocation creates a new `WritingAttempt` + `WritingEvaluation`. Phase 4
therefore MUST NOT claim that reusing Phase 2 persistence alone gives
"same practice retry -> same attempt/evaluation". Phase 4 v1 allows exactly
ONE logical submission per Writing practice; the practice ID is the
ownership/idempotency anchor.

```text
Request submission
  validate learner/practice ownership
  compute deterministic submission fingerprint from the validated essay payload
  BEGIN short DB transaction
    SELECT practice FOR UPDATE
    inspect practice state
    if submitted:
        resolve existing result (same fingerprint) or conflict (different)
    if submission_in_progress:
        return safe submission-in-progress outcome (no new evaluator call)
    claim submission: state = submission_in_progress
      store submission fingerprint + opaque claim token/identity
    COMMIT
  provider evaluation happens OUTSIDE the DB transaction
  validated evaluation result
  BEGIN short finalization transaction
    re-lock practice
    verify claim ownership/token
    atomically create WritingAttempt + WritingEvaluation,
      attach attempt_id to practice, mark submitted
    COMMIT
```

No provider/network call happens while the practice row-lock transaction is
open.

### 10.1 Fingerprint semantics

The fingerprint distinguishes retry of the same submitted essay from an
attempt to replace a practice submission with a different essay:

- after successful submission, same fingerprint -> return the existing
  persisted attempt/evaluation result, no new provider call;
- different fingerprint -> explicit practice-already-submitted conflict, no
  provider call;
- during `submission_in_progress`, same or different request -> MUST NOT start
  another evaluator/provider call; return a stable safe in-progress/conflict
  outcome.

Exact HTTP status/error codes are frozen at P4-12; semantics are frozen now.
Do NOT use a process-local mutex for correctness.

### 10.2 Claim failure semantics

If provider evaluation returns a normalized failure while the current process
owns the active claim:

```text
short transaction: re-lock practice, verify claim token,
  reset practice to generated, clear active claim information, commit
```

This permits a later retry. An already-finalized submission is never erased.

A process crash between claim acquisition and normal cleanup is a known
Phase 4 v1 operational limitation: there is no lease/queue/background
recovery in this Phase. Do NOT invent leases, queues, Celery, Redis, or
distributed job infrastructure. Document abandoned-claim recovery as a known
limitation; correctness is preferred over an unsafe timeout that could start
two provider evaluations simultaneously.

## 11. Atomic attempt/evaluation/link finalization

A provider result MUST NOT be persisted as `WritingAttempt + WritingEvaluation`
and only afterward separately linked to the practice (that could orphan
attempts/evaluations if the link fails). One atomic finalization transaction
must commit together:

```text
WritingAttempt
+ WritingEvaluation
+ practice.attempt_id association
+ practice submitted state
```

This may require a SMALL, focused, Phase 4-compatible refactor of the existing
Writing persistence internals so the accepted Phase 2 validation/model
mapping can participate in an externally owned transaction. The preferred
direction: extract/reuse validated model-building or transaction-neutral
persistence helpers from the existing Phase 2 persistence service, preserving
`/writing/evaluate` behavior unchanged. This requirement is frozen in P4-10.

**Authorized by the Graph:** the focused composition refactor above.
**NOT authorized:** changing Phase 2 scoring, evaluation semantics, rubric
policy, `WritingEvaluation` data, or duplicating a second unrelated Writing
persistence implementation.

## 12. Persistence design

One main durable Phase 4 table: `writing_practices`. No separate
`PracticeSession` table by default (a practice row plus its status IS the
session association).

Conceptual responsibilities (exact schema shape belongs to P4-04/P4-05; the
following invariants are frozen now):

- identity (PK);
- learner ownership (`learner_id` FK -> `learners`);
- originating recommendation (`recommendation_id` FK ->
  `practice_recommendations`); the DB must guarantee the recommendation
  belongs to the same learner (composite ownership FK below);
- authoritative `target_skill` (copied from the recommendation; generator
  output must match it);
- generated content (`question`, `focus_objective`, `instructions`,
  `checkpoints`, `practice_type`) — exists ONLY for successful generation;
  `question` is the authoritative Task 2 question used for any later
  evaluation of this practice;
- generator provenance (`provider`, `model`, `prompt_version`,
  `thinking_mode`) and generation policy version;
- submission lifecycle/claim state, submission fingerprint, claim
  identity/token;
- `attempt_id` FK -> `writing_attempts`, nullable before submission,
  **`ON DELETE RESTRICT` / NO ACTION** (never SET NULL), unique if one
  attempt cannot belong to two practices, and never replaced once attached;
- `created_at`, `updated_at`.

No generic memory/events table. No failed-generation rows.

**Composite ownership FK (frozen):** `writing_practices` must persist BOTH
`recommendation_id` and `learner_id`, and the database must enforce that the
recommendation belongs to the same learner — NOT service-layer validation
alone. Using the accepted Phase 3 composite ownership pattern (the
`LearningUpdate` ownership candidate key precedent):

```text
FOREIGN KEY (recommendation_id, learner_id)
  REFERENCES practice_recommendations (id, learner_id)
  ON DELETE RESTRICT
```

This requires ONE minimal additive schema hardening to the existing
`practice_recommendations` table: the candidate key
`UNIQUE(id, learner_id)`. This does NOT change planner behavior, state
behavior, decision semantics, recommendation identity, or Phase 3
application logic; it exists only to support database-enforced Phase 4
ownership. Exact constraint names belong to P4-05/P4-06.

### 12.1 Required database invariants (design level)

- `UNIQUE(recommendation_id)` — at most one durable practice per eligible
  practice recommendation (idempotency anchor; the composite FK does NOT
  replace it; both are required).
- `UNIQUE(id, learner_id)` candidate key on `practice_recommendations`
  (Phase 4-added; referenced by the composite FK).
- Composite ownership FK: `writing_practices(recommendation_id, learner_id)
  -> practice_recommendations(id, learner_id)` `ON DELETE RESTRICT` — a row
  cannot claim a recommendation from Learner A while storing
  `learner_id` of Learner B.
- One practice belongs to one learner.
- Only `decision_type = practice` recommendations are eligible for a row.
- `attempt_id` nullable before submission; once attached it cannot be
  replaced; `attempt_id` unique.
- Practice attempt FK uses RESTRICT/NO ACTION (auditability: deleting the
  attempt must not silently destroy `practice -> attempt -> evaluation ->
  learning update` traceability).
- A submitted practice cannot be overwritten with a new essay.
- The submission claim prevents two simultaneous evaluator executions.
- All exact constraint names belong to P4-05/P4-06.

## 12a. Submission question authority (frozen)

A Phase 4 practice already contains the authoritative generated IELTS Task 2
question. The learner submission API MUST NOT accept a client-controlled
replacement question.

- Phase 4 submission input conceptually contains **essay only** (plus
  identifiers from route/context); it never duplicates a trusted question.
- The service constructs the existing Phase 2 `WritingSubmission`
  internally:

  ```text
  WritingSubmission(
      question=persisted_practice.question,   # authoritative
      essay=validated_user_essay,             # untrusted
  )
  ```

  This preserves the existing Phase 2 evaluation contract unchanged while
  preventing the client from changing the practice question after generation.
- The deterministic submission fingerprint is based on the authoritative
  validated submission payload; because the question comes from the persisted
  practice, the fingerprint conceptually covers practice identity + persisted
  authoritative question + validated essay (or an equivalent deterministic
  representation). The client cannot alter the question used for evaluation.
  Exact fingerprint encoding/hash belongs to P4-02/P4-04 implementation
  policy; the invariant is frozen now.

## 13. Closed-loop completion (frozen definition)

Phase 4 closed-loop completion is the authoritative trace:

```text
practice has a persisted WritingAttempt
  and that attempt has one persisted WritingEvaluation
  and that evaluation has been applied through Phase 3 (LearningUpdate exists)
  and the resulting PracticeRecommendation exists
```

No duplicated `practice.completed` flag unless a later implementation node
demonstrates a real need.

The next recommendation produced by completion may itself be `practice` or
`no_practice`; both are valid successful closed-loop results. If it is
`no_practice`, completion still succeeds and returns/exposes that
recommendation; it does NOT automatically call the generator. **Never create
an automatic `complete -> generate next practice` loop.** Generation remains
an explicit later client/application action.

## 14. Generator contract boundary

Free-form model text never becomes the database contract. The generation
policy (`P4-03`) freezes a structured boundary before implementation:

- Input authority: the accepted `PracticeRecommendation` (target skill,
  learner target, reason codes, planner version, decision type, snapshot) —
  read-only.
- Structured output: `GeneratedWritingPractice` with `practice_type`,
  `target_skill`, `question`, `focus_objective`, `instructions`, `checkpoints`,
  and generator policy version + provider/model/prompt/thinking provenance.
- **Authority mirroring:** any generated field that mirrors
  application-owned authority (e.g. `target_skill`) is validated against the
  persisted recommendation; mismatch = invalid provider response, no row,
  safe normalized failure.
- Prompt ownership: application-owned prompt templates with a frozen
  `prompt_version`; the policy defines supported skills, Task 2 scope, content
  constraints, maximum sizes, safety constraints, fallback behavior, retry
  classes, idempotency, and provenance requirements.

## 15. LLM architecture decision

The existing Phase 2 `LLMProvider` protocol and `RetryingProvider` are
Writing-evaluator-specific (`evaluate_writing`); they cannot directly wrap a
generator. Phase 4 reuses `ProviderError`, `ProviderErrorCategory`,
`ProviderErrorContext`, `ProviderRetryPolicy`, accepted retryable category
semantics, and bounded retry/backoff rules — but adds the smallest focused
abstraction:

```text
PracticeGenerator (Protocol, async)
  generate_practice(request: PracticeGenerationRequest) -> GeneratedWritingPractice
```

with the frozen retry composition:

```text
PracticeGenerator
  -> RetryingPracticeGenerator (small focused wrapper implementing the
     PracticeGenerator protocol, reusing ProviderRetryPolicy/backoff rules)
  -> DeepSeekPracticeGenerator
```

- `DeepSeekPracticeGenerator` implements the protocol using application-owned
  prompt templates and the accepted `httpx.AsyncClient` injection pattern.
- `FakePracticeGenerator` provides deterministic, policy-valid practices for
  tests and CI (no live key, no network).
- No second generic model gateway, no Agent framework, no Tool framework.
- No generic retry-framework refactor unless a later implementation node
  proves it materially simpler AND external review approves it; the default
  plan is the focused `RetryingPracticeGenerator`.

## 16. Service boundaries (frozen; human-time separation)

Generation and learner submission are separated by HUMAN TIME. The learner
may receive a practice and submit it minutes/hours/days later. These are
separate services, never one synchronous orchestration:

- **P4-09 — Practice Generation Service**: `recommendation -> generated
  persisted practice`. STOPS there.
- **P4-10 — Practice Submission Integration**: `existing practice ->
  submission claim -> provider evaluation -> atomic
  attempt/evaluation/practice-link finalization`. STOPS there.
- **P4-11 — Closed-loop Completion & Replan Service**: `persisted submitted
  practice -> persisted WritingEvaluation -> existing Phase 3 apply -> new
  Learner State -> next PracticeRecommendation -> expose closed-loop result`.
  P4-11 MUST NOT generate a new practice. A future client call may use the
  resulting next recommendation to call P4-09.

The accepted lifecycle is `Generate -> HUMAN PRACTICE TIME -> Submit/Evaluate
-> Apply/Replan`. Do not build one giant synchronous workflow endpoint.

## 17. Provider/network rules

- All provider/network calls happen OUTSIDE database transactions.
- Generation: generate (outside txn) -> short persist transaction.
- Submission: claim (short txn) -> provider evaluation (outside txn) ->
  atomic finalization (short txn).
- A persisted evaluation is reusable without re-invoking the LLM (Phase 3
  idempotency remains authority).
- No live DeepSeek key is required for any Phase 4 test or CI run.

## 18. Test strategy

Required coverage:

- pure generation-policy tests (frozen branches, eligibility gating,
  no_practice/cold-start semantics, provenance, constraints);
- schema tests;
- generator-contract tests and Fake-generator determinism;
- provider adapter tests without live network (injected client);
- retry-wrapper tests for the focused `RetryingPracticeGenerator`;
- real PostgreSQL persistence tests (ownership, unique anchors, FKs,
  RESTRICT semantics);
- **real PostgreSQL cross-owner FK failure test (required):** Learner A owns
  Recommendation RA; Learner B exists; persisting
  `writing_practices(recommendation_id = RA.id, learner_id = B.id)` MUST fail
  at the DATABASE level (composite ownership FK violation). Accepting only a
  service-layer rejection is insufficient — the database constraint itself
  must be proven. Also test that a valid same-owner insert succeeds;
- migration upgrade/downgrade/re-upgrade + drift + single head (including the
  Phase 4-added candidate key on `practice_recommendations` being added by
  upgrade and removed by downgrade);
- generation idempotency: first generate, retry returns same practice,
  concurrent race -> at most one durable row, losing request resolves winner
  (documented: provider may be invoked more than once);
- submission idempotency: first submit, same-fingerprint retry returns
  existing result, different-fingerprint conflict, in-progress safe outcome;
- submission concurrency: two concurrent submissions -> only one claim, only
  one authorized evaluator execution, only one `WritingAttempt`, only one
  `WritingEvaluation`, one `practice.attempt_id`, no orphan writing records
  (real PostgreSQL; no process-local lock; if PostgreSQL row-lock waiting is
  central, prove it with PostgreSQL-native observation as in Phase 3);
- rollback (generation failure leaves no row; claim failure resets to
  generated; finalization atomicity);
- safe API failure tests (no raw leakage; stable error contract);
- full Phase 1/2/3/4 regression, no required skip, no live model;
- Docker clean-checkout validation; PR CI with no DeepSeek credentials.

The final closed-loop integration test must demonstrate, without a live model:

```text
Recommendation (practice) -> Practice -> Submission -> Evaluation
-> Learning Apply -> New State -> New Recommendation
```

using the Fake generator and the existing Fake/isolated evaluation path. Both
a `practice` and a `no_practice` next recommendation are valid outcomes.

## 19. Node state model

`NOT_STARTED` / `READY` / `ACTIVE` / `COMPLETE` / `FIXING`, mirroring Phase 3.
All nodes are currently `NOT_STARTED`; nothing is authorized to run until a
separate explicit execution authorization activates `P4-01`.

**Graph execution rule (frozen):** a node becomes `READY` only when EVERY
dependency listed for that node is `COMPLETE`. "Unlocks" means the dependency
may become satisfiable; it does NOT override other unmet dependencies. In
particular `P4-09` becomes `READY` only when `P4-04`, `P4-06`, AND `P4-08`
are all `COMPLETE` — `P4-06` alone or `P4-08` alone is insufficient.

## 20. Dependency graph

```text
P4-01 Phase 4 Baseline & Transition
  -> P4-02

P4-02 Adaptive Writing Practice Product Contract
  -> P4-03

P4-03 Writing Practice Generation Policy
  -> P4-04 -> P4-05 -> P4-06
  -> P4-07 -> P4-08

P4-04 Practice Domain / API Schemas
  -> P4-05

P4-05 Practice Persistence Models
  -> P4-06

P4-07 Practice Generator Contract
  -> P4-08

P4-08 DeepSeek Practice Generator + deterministic test fake
  (required by P4-09: an implemented generator + fake, not merely the
   interface)

P4-06 + P4-04 + P4-08
  -> P4-09  Practice Generation Service

P4-09 + P4-02 + P4-06
  -> P4-10  Practice Submission Integration

P4-10
  -> P4-11  Closed-loop Completion & Replan Service

P4-11
  -> P4-12  Practice APIs

P4-12
  -> P4-13  Idempotency / Failure / Concurrency Hardening

P4-13
  -> P4-14  Closed-loop Integration Validation

P4-14
  -> P4-15  Docker / Documentation / Reproducibility

P4-15
  -> P4-16  Internal Final Audit & External Review Handoff

P4-16
  -> WORKBUDDY STOP / EXTERNAL REVIEW HANDOFF
```

Dependency reasons:

- `P4-03` is the single authority for schema shape (`P4-04`), the
  persistence contract (`P4-05`), the migration (`P4-06`), and the generator
  contract (`P4-07`); it does NOT directly unlock `P4-05`/`P4-06`, which
  depend on `P4-04`/`P4-05` respectively.
- `P4-03 -> P4-07`: the policy defines the generator contract.
- `P4-07 -> P4-08 -> P4-09`: P4-09 requires an implemented generator plus the
  deterministic fake (P4-07 alone is only the interface).
- `P4-09 + P4-02 + P4-06 -> P4-10`: submission semantics come from the product
  contract, the practice table must exist, and generation must be usable.
- No new nodes are added merely to fix dependency arrows.

---

## 21. Node definitions

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
- **Purpose:** Freeze exactly what Phase 4 means by Practice, Submission,
  completion, and closed-loop result; the decision-gated semantics
  (`practice` vs `no_practice`, cold-start boundary from section 6); the
  lifecycle vocabulary from section 9; the submission-question authority rule
  from section 12a (the practice owns the generated question; submission means
  the learner submits an essay for that persisted practice; the persisted
  question is reused during evaluation; a caller cannot substitute another
  question); and the smallest useful user story.
- **Dependencies:** `P4-01`.
- **Inputs / authority:** Phase 3 recommendation contract; Phase 2 evaluation
  pipeline.
- **Deliverables:** accepted definitions, status vocabulary, submission-claim
  and completion semantics; the submission question-authority rule; the
  primary end-to-end acceptance story starting from an ESTABLISHED learner
  state that yields `decision_type = practice` (see section 24), reflecting
  `Practice(question) -> learner submits essay -> server constructs
  WritingSubmission(question from Practice, essay from user) -> Phase 2
  evaluation`.
- **Acceptance criteria:** the story is unambiguous, testable end-to-end with
  fakes, and all Phase 4 API behavior traces to it; no_practice/cold-start
  behavior is explicit; the submission API accepts an essay, never a
  replacement question.
- **Forbidden scope:** lesson generation, curriculum, bootstrap practice,
  other skills.
- **Failure / FIXING:** ambiguous session/completion semantics keep `P4-02` in
  `FIXING`.
- **Unlocks:** `P4-03`.

### P4-03 — Writing Practice Generation Policy

- **Type:** design / policy
- **Purpose:** Freeze `writing-practice-generation-v1` BEFORE any generator
  implementation.
- **Dependencies:** `P4-02`.
- **Inputs / authority:** accepted recommendation contract.
- **Deliverables:** `docs/WRITING_PRACTICE_GENERATION_POLICY.md` defining input
  authority (decision-gated: `practice` only), supported target skills, Task 2
  scope, structured output requirements, authority-mirroring validation,
  prompt ownership + version, provider provenance, retry classes, content
  limits, safety constraints, SUCCESS-ONLY idempotency behavior, and failure
  semantics. Explicit: no LLM chooses `target_skill`; no generation for
  `no_practice`.
- **Acceptance criteria:** every frozen rule is testable; the policy states
  "Recommendation controls WHAT; generator controls HOW."
- **Forbidden scope:** state/planner override, multi-skill content,
  no_practice generation.
- **Failure / FIXING:** free-form contract, missing limits, eligibility
  ambiguity, or state-authority ambiguity keeps `P4-03` in `FIXING`.
- **Unlocks:** `P4-04`, `P4-07`.

### P4-04 — Practice Domain / API Schemas

- **Type:** schema
- **Purpose:** Freeze strict Pydantic v2 schemas for generated practice,
  submission claim, submission fingerprint, lifecycle state, and API
  boundaries (mirroring Phase 2/3 schema discipline).
- **Dependencies:** `P4-03`.
- **Inputs / authority:** generation policy; `P4-02` product contract.
- **Deliverables:** schemas for `GeneratedWritingPractice`, submission
  claim/response, fingerprint, practice response, closed-loop result, and safe
  error mapping additions only if required. The schema design MUST distinguish
  Phase 2 `WritingSubmission` (question + essay) from Phase 4
  `PracticeSubmission` (**essay only**, plus identifiers from route/context,
  never a duplicated trusted question); the Phase 4 service composes the
  trusted practice question with the untrusted essay into the existing Phase 2
  `WritingSubmission` internally. `WritingSubmission` itself is NOT redesigned.
- **Acceptance criteria:** schema tests pass; no ORM/service/LLM behavior in
  schemas.
- **Forbidden scope:** planner/state schema redesign; redesigning
  `WritingSubmission`.
- **Failure / FIXING:** mutable defaults, missing constraints, or leakage of
  provider internals keeps `P4-04` in `FIXING`.
- **Unlocks:** `P4-05` (a dependency of `P4-09`; `P4-09` becomes READY only
  when `P4-04`, `P4-06`, and `P4-08` are all COMPLETE).

### P4-05 — Practice Persistence Models

- **Type:** database
- **Purpose:** Implement the minimal `writing_practices` model (section 12)
  plus the Phase 4 ownership hardening.
- **Dependencies:** `P4-04`.
- **Inputs / authority:** frozen schemas; section 12/12a invariants (including
  the composite ownership FK and the `practice_recommendations` candidate
  key); Phase 3 composite ownership pattern (the `LearningUpdate` ownership
  candidate-key precedent).
- **Deliverables:** SQLAlchemy 2.x `writing_practices` model with learner
  ownership, `recommendation_id` + `learner_id`, the composite ownership FK
  design `(recommendation_id, learner_id) ->
  practice_recommendations(id, learner_id)` RESTRICT, `UNIQUE
  (recommendation_id)`, `UNIQUE(attempt_id)` if retained by accepted design,
  claim/fingerprint columns, `attempt_id` RESTRICT semantics, timestamps,
  provenance columns; plus the narrow additive candidate key
  `UNIQUE(id, learner_id)` on the `practice_recommendations` model.
- **Acceptance criteria:** model tests (constraints, anchors, ownership,
  composite FK structure, RESTRICT semantics) pass; no business logic in
  models; the model structure supports the composite ownership invariant.
- **Forbidden scope:** memory/events tables, curriculum tables,
  failed-generation rows, planner/state policy changes.
- **Failure / FIXING:** broken anchors, missing ownership, SET NULL attempt
  FK, missing composite ownership support, or generic-history design keeps
  `P4-05` in `FIXING`.
- **Unlocks:** `P4-06`.

### P4-06 — Alembic Migration

- **Type:** database
- **Purpose:** Add reversible migration `0004_writing_practice` (single head).
- **Dependencies:** `P4-05`.
- **Inputs / authority:** accepted model; section 12/12a invariants.
- **Deliverables:** upgrade/downgrade/re-upgrade verified on real PostgreSQL;
  drift check; constraint tests (unique anchors, composite ownership FK,
  RESTRICT FKs). The migration MAY perform exactly TWO additive changes:
  (1) create `writing_practices` and its Phase 4 constraints; (2) add the ONE
  narrow additive Phase 3 candidate key
  `UNIQUE(id, learner_id)` on `practice_recommendations` to support the
  Phase 4 composite ownership FK.
- **Acceptance criteria:** linear history `0001 -> 0002 -> 0003 -> 0004`,
  single head; upgrade -> downgrade -> re-upgrade valid on real PostgreSQL.
  Downgrade removes ONLY Phase 4 additions: drop `writing_practices` and its
  Phase 4 constraints, THEN drop the Phase 4-added
  `UNIQUE(id, learner_id)` candidate key from `practice_recommendations`; no
  pre-existing Phase 3 constraint is removed or altered.
- **Forbidden scope:** any other Phase 2/3 schema change: Phase 2 scoring,
  Writing evaluation structure/meaning, Phase 3 state policy, Phase 3 planner
  policy, `LearningEvidence` semantics, `LearnerSkillState` semantics,
  `PracticeRecommendation` decision semantics.
- **Failure / FIXING:** drift, non-reversible downgrade, head conflicts, or
  unauthorized Phase 2/3 alteration keeps `P4-06` in `FIXING`.
- **Unlocks:** `P4-09` (a dependency of `P4-09`, which becomes READY only
  when `P4-04`, `P4-06`, and `P4-08` are all COMPLETE).

### P4-07 — Practice Generator Contract

- **Type:** domain logic (interface)
- **Purpose:** Freeze the `PracticeGenerator` protocol and request/response
  types from `P4-03`.
- **Dependencies:** `P4-03`.
- **Inputs / authority:** generation policy.
- **Deliverables:** protocol with `generate_practice`, typed request (authority
  values only) and `GeneratedWritingPractice` response; authority-mirroring
  validation requirement; failure normalization reusing `ProviderError`.
- **Acceptance criteria:** contract tests with a stub pass; no state mutation;
  mismatch of mirrored authority fields is invalid.
- **Forbidden scope:** generic gateway/tool abstractions.
- **Failure / FIXING:** contract leakage, untyped output, missing authority
  validation, or state write attempts keep `P4-07` in `FIXING`.
- **Unlocks:** `P4-08`.

### P4-08 — DeepSeek Practice Generator + deterministic test fake

- **Type:** provider
- **Purpose:** Implement the production generator, the focused retry wrapper,
  and the deterministic fake.
- **Dependencies:** `P4-07`.
- **Inputs / authority:** `P4-03` policy; `P4-07` contract.
- **Deliverables:** `DeepSeekPracticeGenerator` (reusing the accepted httpx
  injection and `ProviderError`/backoff patterns), `RetryingPracticeGenerator`
  (focused wrapper implementing `PracticeGenerator`), and
  `FakePracticeGenerator` (deterministic, policy-valid content).
- **Acceptance criteria:** adapter tests with injected client (no live
  network); retry-wrapper tests; fake determinism tests; provenance recorded;
  authority fields never override application input.
- **Forbidden scope:** network in tests; target-skill authority; generic
  retry-framework refactor.
- **Failure / FIXING:** live-network test coupling, contract drift, or
  authority override keeps `P4-08` in `FIXING`.
- **Unlocks:** `P4-09`.

### P4-09 — Practice Generation Service

- **Type:** application service
- **Purpose:** Orchestrate one SUCCESS-ONLY, decision-gated, idempotent
  practice generation: `recommendation -> generated persisted practice`. STOPS
  there (no submission, no apply, no replan).
- **Dependencies:** `P4-04` + `P4-06` + `P4-08` (an implemented generator AND
  deterministic fake are required; the `P4-07` interface alone is not enough).
  `P4-09` becomes `READY` only when ALL THREE are `COMPLETE`.
- **Inputs / authority:** persisted recommendation, learner, generator,
  session, unique anchor, composite ownership FK.
- **Deliverables:** service that validates learner/recommendation ownership
  and `decision_type = practice`, returns an existing practice on retry,
  returns a deterministic no-practice outcome for `no_practice`, runs the
  generator OUTSIDE the transaction, validates mirrored authority fields, and
  persists at most one `writing_practices` row (winner resolution on
  `UNIQUE(recommendation_id)`).
- **Acceptance criteria:** PostgreSQL tests for first generate, idempotent
  retry, no_practice -> zero rows, cold_start -> zero rows + no generator
  call, cross-learner conflict, provider failure -> no row, rollback,
  provenance retention, concurrent first-generation -> exactly one durable
  row (losing request resolves the winner), and the database-level ownership
  mismatch negative case (section 18).
- **Forbidden scope:** LLM inside transaction; state mutation; submission or
  apply orchestration.
- **Failure / FIXING:** duplicate practices, partial writes, no_practice
  rows, or provider coupling keeps `P4-09` in `FIXING`.
- **Unlocks:** `P4-10`.

### P4-10 — Practice Submission Integration

- **Type:** application service
- **Purpose:** Implement the frozen submission-claim protocol (section 10) for
  `existing practice -> claim -> provider evaluation -> atomic
  attempt/evaluation/practice-link finalization`. STOPS there.
- **Dependencies:** `P4-09`, `P4-02`, `P4-06`.
- **Inputs / authority:** practice identity, validated essay payload, Phase 2
  evaluation pipeline, session.
- **Deliverables:** the explicit submission flow — load persisted practice,
  verify ownership, take `persisted_practice.question` as AUTHORITATIVE,
  validate the learner essay, compute the submission fingerprint, claim the
  practice (`FOR UPDATE`, state, fingerprint, claim token), construct the
  Phase 2 `WritingSubmission(question=persisted_practice.question,
  essay=validated_user_essay)` internally, evaluate OUTSIDE the transaction,
  then one atomic finalization transaction creating `WritingAttempt` +
  `WritingEvaluation` + `practice.attempt_id` + `submitted` together — via a
  small focused composition refactor of Phase 2 persistence internals (allowed
  by section 11) that leaves `/writing/evaluate` unchanged. Never accept a
  replacement client question for a Phase 4 practice submission.
- **Acceptance criteria:** real-PostgreSQL tests for first submit,
  same-fingerprint retry (existing result, no provider call),
  different-fingerprint conflict, in-progress safe outcome, claim-failure
  reset to generated, atomic finalization (no orphan attempt/evaluation),
  RESTRICT deletion semantics, question-authority (client cannot substitute a
  question), and concurrent submission -> one claim/one evaluator/one
  attempt/one evaluation.
- **Forbidden scope:** changing Phase 2 scoring/rubric/evaluation semantics;
  duplicating a second Writing persistence implementation; process-local
  correctness locks; accepting a client-controlled question.
- **Failure / FIXING:** broken attempt link, duplicate submission, orphan
  writing records, question substitution, or Phase 2 bypass keeps `P4-10` in
  `FIXING`.
- **Unlocks:** `P4-11`.

### P4-11 — Closed-loop Completion & Replan Service

- **Type:** application service
- **Purpose:** For a persisted submitted practice: `persisted WritingEvaluation
  -> existing Phase 3 apply -> new Learner State -> next PracticeRecommendation
  -> expose closed-loop result`. MUST NOT generate a new practice; MUST NOT
  call the generator.
- **Dependencies:** `P4-10`.
- **Inputs / authority:** submitted practice, its persisted evaluation,
  existing Phase 3 `apply_writing_evaluation`, session.
- **Deliverables:** deterministic completion returning the persisted next
  recommendation (which may be `practice` or `no_practice` — both valid);
  reuse of Phase 3 apply idempotency (same evaluation retry -> no duplicate
  evidence/state/recommendation).
- **Acceptance criteria:** full closed-loop PostgreSQL test with fakes (no
  live model); exactly one next recommendation; `no_practice` next decision
  succeeds without generation.
- **Forbidden scope:** generation; automatic complete->generate loop; a
  second learner-state update mechanism; LLM state mutation.
- **Failure / FIXING:** missing replan result, duplicate apply effects, or
  generation coupling keeps `P4-11` in `FIXING`.
- **Unlocks:** `P4-12`.

### P4-12 — Practice APIs

- **Type:** API
- **Purpose:** Thin routes supporting SEPARATE lifecycle actions:
  generate/resolve next eligible Writing practice; inspect one practice;
  submit one practice; complete/apply/replan or expose completion result.
  Exact paths are frozen here; NO single giant
  `POST /practice/complete-everything` endpoint.
- **Dependencies:** `P4-11`.
- **Inputs / authority:** frozen schemas, services, existing error contract.
- **Deliverables:** safe endpoints exposing the auditable decision,
  no-practice outcomes, submission status, and closed-loop result; no raw
  internals.
- **Acceptance criteria:** API tests for generate (incl. no_practice and
  cold-start outcomes), idempotent retry, inspect, submit (claim/conflict/
  in-progress), complete, and safe 4xx/5xx; no provider call in tests.
- **Forbidden scope:** frontend-specific APIs; business logic in routes;
  merged generate+submit+complete endpoints.
- **Failure / FIXING:** route business logic, unsafe leakage, lifecycle
  endpoint merging, or missing closed-loop fields keeps `P4-12` in `FIXING`.
- **Unlocks:** `P4-13`.

### P4-13 — Idempotency / Failure / Concurrency Hardening

- **Type:** test / hardening
- **Purpose:** Prove database-safe duplicate and concurrent behavior against
  real PostgreSQL for BOTH generation and submission.
- **Dependencies:** `P4-12`.
- **Inputs / authority:** services, APIs, unique anchors, claim protocol,
  per-learner/per-practice row locks.
- **Deliverables:** generation race tests (same recommendation, two
  concurrent requests -> at most one durable row; both logical callers resolve
  the same practice; provider invocation count is NOT asserted — documented
  limitation); submission race tests (two concurrent submissions -> only one
  claim owner, only one authorized evaluator execution, one `WritingAttempt`,
  one `WritingEvaluation`, one `practice.attempt_id`, no orphan writing
  records); PostgreSQL-native lock observation only where the implemented
  claim schedule makes it central (per Phase 3 precedent).
- **Acceptance criteria:** no duplicate practices/attempts/evaluations;
  deterministic final state; no process-local correctness lock.
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
- **Acceptance criteria:** the section 24 acceptance story passes end-to-end;
  every Phase 1/2/3 regression remains green; both `practice` and `no_practice`
  next-decision outcomes covered.
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

### P4-16 — Internal Final Audit & External Review Handoff

- **Type:** documentation
- **Purpose:** Consolidate internal validation evidence and prepare the branch
  for external review. P4-16 does NOT declare external acceptance.
- **Dependencies:** `P4-15`.
- **Inputs / authority:** node statuses, policies, commits, PostgreSQL/API/
  Docker/CI-eligible evidence.
- **Deliverables:** `docs/PHASE4_AUDIT.md` with node status, policy versions,
  commit checkpoints, closed-loop proof, generation/submission idempotency and
  concurrency results, migration head, security/scope review, known
  limitations (exactly-once provider invocation not guaranteed; abandoned-claim
  recovery), and next-phase recommendation.
- **Acceptance criteria:** evidence complete and internally consistent.
  After P4-16 succeeds the status is `P4-01 ... P4-15 = COMPLETE`,
  `P4-16 = INTERNAL_AUDIT_COMPLETE`, `PHASE 4 = FINAL_REVIEW_PENDING`, and
  WorkBuddy execution STOPS.
- **Forbidden scope:** claiming external review approval, PR CI green, master
  merge, or Phase 4 acceptance.
- **Failure / FIXING:** missing evidence or unrun required validation keeps
  `P4-16` in `FIXING`.
- **Unlocks:** WORKBUDDY STOP / EXTERNAL REVIEW HANDOFF.

---

## 22. External gate (post-P4-16 process)

This process occurs OUTSIDE automatic P4 node execution:

```text
P4-16 internal audit
  -> STOP WorkBuddy
  -> ChatGPT external code review
  -> FIXING loop if needed
  -> create PR
  -> GitHub pull_request CI
  -> CI green
  -> final external approval
  -> explicit user merge authorization
  -> merge master
  -> master push CI
  -> Phase 4 accepted
```

Phase 5 remains NOT_STARTED throughout. WorkBuddy never claims any of these
external events before they occur.

## 23. Database safety

- All destructive/integration work uses the isolated test database guarded by
  `validate_test_database_url` (test token + never the development DB).
- No `.env` committed; no secrets; environment-based configuration only.
- Downgrade/truncate only on verified test-only databases.
- Migration contract: linear history `0001_phase1 -> 0002_writing ->
  0003_learning -> 0004_writing_practice`, single head, reversible, zero drift.

## 24. Primary end-to-end acceptance story

Start from an ESTABLISHED learner state that already yields
`PracticeRecommendation: decision_type = practice, target_skill =
task_response`.

Example: learner target 7.0; TR 6.0, CC 6.5, LR 6.5, GRA 6.5; Phase 3
recommends `task_response`.

```text
existing Phase 3 recommendation (practice, task_response)
  -> P4 generate targeted Task Response practice (persisted question)
  -> persist one writing_practices row
  -> human submission (learner submits ESSAY only; the practice question is
     authoritative and reused, never replaced by the client)
  -> claim submission (fingerprint + claim token)
  -> server constructs WritingSubmission(question from practice, essay from
     user) -> Fake/evaluation provider OUTSIDE DB transaction
  -> atomically persist WritingAttempt + WritingEvaluation + practice link
  -> existing Phase 3 apply
  -> new LearnerSkillState
  -> new PracticeRecommendation (practice OR no_practice; both valid)
```

The complete end-to-end test runs with fakes and isolated PostgreSQL. No live
DeepSeek.

## 25. Git rules

- Work on `phase/4-adaptive-writing-practice` (from accepted `master`).
- Never push directly to `master`.
- One node = one focused checkpoint commit (additive; no history rewriting).
- After the Graph is accepted and execution is separately authorized, each
  completed node is committed, pushed, and the Graph status updated before the
  next READY node activates.

## 26. STOP conditions

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

## 27. Execution authority

This Graph does NOT authorize runtime execution. After external review of this
Graph, a separate explicit user authorization is required to activate `P4-01`.
No continuous execution begins automatically.

## 28. Final acceptance criteria (Phase 4)

- The closed loop `Recommendation (practice) -> Practice -> Submission ->
  Evaluation -> Apply -> New State -> New Recommendation` is implemented and
  proven with fakes on isolated PostgreSQL.
- At most one durable practice per eligible recommendation; zero rows for
  `no_practice`/cold-start; idempotent retries; explicit ownership conflicts;
  submission claim protocol enforced; atomic finalization with no orphan
  writing records.
- Provider calls stay outside transactions; a persisted evaluation is reusable
  without re-invoking the LLM; Phase 3 apply idempotency is the sole state
  update mechanism.
- All Phase 1/2/3 regressions remain green; full suite passes with no required
  skip and no live DeepSeek key; Docker clean-checkout validation passes.
- Single Alembic head; no forbidden scope; no secrets; truthful documentation.

## 29. Phase 5 boundary

Phase 5 (not designed here) would introduce long-term learning memory,
reflection, and possibly additional skills. Phase 4 deliberately builds
transactional practice history only — not a generic memory or events system.

---

**Design status:** GRAPH READY FOR EXTERNAL REVIEW — no runtime execution
authorized. All `P4-01` … `P4-16` nodes are `NOT_STARTED`. Phase 5 remains
`NOT_STARTED`.

---

## 30. Execution record

### P4-01 — Phase 4 Baseline & Transition — `COMPLETE`

Baseline verified before any Phase 4 runtime work (commit
`docs: record Phase 4 baseline transition`):

- branch `phase/4-adaptive-writing-practice` based on accepted `master` @
  `8cb0b73` (`feat: complete Phase 3 learner state and adaptive planning
  (#7)`); Phase 3 merged and master CI accepted.
- single Alembic head `0003_learning`; history linear
  `0001_phase1 -> 0002_writing -> 0003_learning`.
- full Phase 1/2/3 regression on isolated PostgreSQL: **705 passed, 1 warning**
  (recorded Starlette `httpx` deprecation); required PostgreSQL integration
  tests executed, none skipped.
- no Phase 4 runtime implementation present; branch clean before
  implementation.

`P4-02` is now `READY`.
