# Phase 8 — Core Learning Agent Orchestration v1

## Document status

**IMPLEMENTATION COMPLETE — External Implementation Review pending.** P8-01 and
P8-02 froze the contract; External Design Review authorized the implementation.
P8-03 through P8-12 are complete and P8-13 is internally audited on
`phase/8-core-learning-agent-v1`. The implementation remains a bounded,
Writing-only Core Learning Agent v1; Phase 9 is not started.

Phase 8 introduces one deterministic, Writing-only Core Learning Agent. It
coordinates existing application services during one explicitly invoked, bounded
turn. It does not replace learner state, Memory, the Planner, evaluators,
generators, or practice lifecycle services; it calls services directly and never
calls FastAPI routes.

## Dependency graph

```text
START
  -> P8-01 Baseline & Core Agent Capability Audit [COMPLETE]
  -> P8-02 Core Learning Agent v1 Contract Freeze [COMPLETE]
  -> External Design Review [APPROVED]
  -> P8-03 Versioned Agent Turn Schemas [COMPLETE]
  -> P8-04 Submission-Claim Recovery Metadata [COMPLETE]
  -> P8-05 Authoritative Agent Observation [COMPLETE]
  -> P8-06 Existing-Service Tool Boundary [COMPLETE]
  -> P8-07 Deterministic Action Selector [COMPLETE]
  -> P8-08 Bounded Agent Turn Executor [COMPLETE]
  -> P8-09 Core Agent API [COMPLETE]
  -> P8-10 Chinese-First Agent UX [COMPLETE]
  -> P8-11 Concurrency / Retry / Crash-Recovery Hardening [COMPLETE]
  -> P8-12 Lifecycle Compatibility + E2E / CI [COMPLETE]
  -> P8-13 Internal Final Audit [INTERNAL_AUDIT_COMPLETE]
  -> STOP -> External Implementation Review [PENDING]
```

P8-04 was conditionally required and is now complete. It remains a narrow
extension of existing practice-claim storage, not a generic Agent database. Its
300-second lease,
PostgreSQL-time authority, migration backfill of legacy NULL timestamps, strict
post-upgrade invariant, and shared granular Option A compatibility are frozen
in the policy.

## P8-01 — Baseline & Core Agent Capability Audit — COMPLETE

The following P8-01 findings are historical baseline evidence from before the
implemented Agent runtime; they are retained to preserve the design decision trail.

### Audit method and scope

The audit inspected the actual branch base and the required architecture,
policies, services, ORM models, Pydantic schemas, route/dependency wiring,
browser client and UX, lifecycle/concurrency/idempotency tests, and Chromium
E2E specifications. It was read-only: no tests were executed and no runtime,
migration, frontend, or configuration file was changed.

### Concrete findings

| # | Finding | Evidence and Phase 8 implication |
| --- | --- | --- |
| 1 | No Agent runtime or Agent Turn endpoint exists. | `app/main.py` registers only health, writing, learner, practice, and memory routers; P8 needs an explicit narrow surface. |
| 2 | Current orchestration is split across explicit user actions and web pages. | Writing evaluates then applies; dashboard generates; practice submits then completes. |
| 3 | Initial evaluation is provider-backed then persisted atomically. | `WritingEvaluationService.evaluate()` calls the provider and `WritingEvaluationPersistenceService.persist()` commits the attempt/evaluation pair. |
| 4 | Initial rows are not learner-owned until apply. | `WritingAttempt` and `WritingEvaluation` have no learner id; `LearningUpdate` creates ownership. |
| 5 | Unapplied initial evaluation cannot resume from learner id. | `build_learner_context()` returns `initial_writing`; `test_unapplied_initial_evaluation_is_not_server_recoverable` preserves the limitation. |
| 6 | Initial persistence has no input fingerprint/idempotency key. | Retrying question + essay can make another pair; Agent v1 must exclude initial Writing input. |
| 7 | Apply is atomic and idempotent. | `learning_updates.writing_evaluation_id` is globally unique; duplicate apply resolves the existing result. |
| 8 | Apply serializes same-learner updates without providers. | It locks the learner and does all replay/planning/persistence inside its short transaction. |
| 9 | New applies activate Planner v2; v1 history remains valid. | Apply stores `PLANNER_V2_VERSION`; versioned reconstruction preserves historical v1 decisions. |
| 10 | The Planner owns target choice. | The apply service selects and persists the decision; an Agent must never choose or override `target_skill`. |
| 11 | Memory context is Planner-only and exact-tie-only. | The v2 apply path builds it only after base selection requires it. |
| 12 | Generation is idempotent per recommendation. | `writing_practices.recommendation_id` is unique; `generate_or_resolve()` returns the durable winner. |
| 13 | Generation never holds a DB transaction across the provider. | It releases reads before provider work and uses a short insert transaction afterward. |
| 14 | The generator receives recommendation authority, not Memory. | Its request has id/target/band/reasons/version; no Memory context or audit snapshot is passed. |
| 15 | Practice submission trusts the persisted question. | Client input is essay only; the service constructs trusted writing input from `WritingPractice.question`. |
| 16 | Submission has a durable per-practice claim. | A row lock stores fingerprint and opaque token, and a concurrent follower returns `in_progress` without another evaluation call. |
| 17 | Submission retries are idempotent after finalization. | Same fingerprint returns `reused`; a different essay returns `conflict`; tests prove one durable pair. |
| 18 | Caught provider/finalization failures release only the caller's claim. | The service resets only a matching owned token after a recoverable failure. |
| 19 | Crash recovery for an in-progress claim is missing. | No claimed-at/lease exists; later input deterministically returns `in_progress` and context returns `await_submission`. |
| 20 | Completion safely reuses apply. | `PracticeCompletionService.complete()` finds the persisted evaluation then uses idempotent apply; retry has no duplicate effects. |
| 21 | Completion and next generation are separate durable steps. | Completion persists a new recommendation and never generates; a later observation can resume failed generation. |
| 22 | `writing-context-v1` is not Agent-authoritative. | It chooses latest `LearningUpdate` by `created_at DESC, id DESC`, a frozen Phase 6 contract. |
| 23 | Phase 7 accepted-update chronology is id order. | Policy and `test_owner_bound_recency_uses_acceptance_ids_not_transaction_start_order` freeze `LearningUpdate.id DESC`. |
| 24 | Timestamp and acceptance order can disagree under concurrency. | A direct Agent use of context v1 could act on a recommendation that is not the latest accepted update. |
| 25 | Agent observation must be versioned and separate. | P8 needs `writing-agent-observation-v1` using `LearningUpdate.id DESC`; it must not alter context v1. |
| 26 | Current context supplies deterministic lifecycle branches. | Initial, no action, generate, submit, await, and complete are all represented from persisted data. |
| 27 | Observation is provider-free. | Memory/context reads only persisted rows, and `test_reads_make_zero_provider_calls` guards this. |
| 28 | Routes are thin and already compose dependencies. | The future Agent route may compose DB/provider/generator dependencies, while the Agent calls services directly—not HTTP. |
| 29 | Granular client APIs remain public. | `createApiClient()` exposes evaluate, apply, generate, submit, complete, context, history, and progress separately. |
| 30 | Browser cache is presentation-only. | It stores learner/recommendation navigation data; dashboard reloads server state/context. |
| 31 | Chinese-first UX exposes human boundaries. | Existing dashboard and practice pages ask for first writing or an essay and show processing/recovery states. |
| 32 | Existing tests cover domain safety, not Agent composition. | Apply, generation, submission, completion, context, v1/v2 compatibility, and four Chromium E2E paths exist; Agent schemas/recovery/E2E remain future work. |

### P8-01 conclusions

1. One deterministic controller can coordinate direct service calls; it is not a
   Planner, Memory engine, evaluator, generator, or route-to-route client.
2. `build_learner_context()` stays frozen. P8 needs a separate
   `writing-agent-observation-v1` with latest accepted update by id; no context
   v1 bug fix or evolution is authorized.
3. Initial Writing is excluded from Agent Turn v1. Existing granular evaluate
   and apply remain the bootstrap because the pre-apply crash cannot be recovered
   from learner id alone.
4. No generic Agent-run table, event stream, or framework is justified. Existing
   durable practice/evaluation/update rows anchor all accepted Agent v1 inputs.
5. P8-04 is required before Agent-owned practice essay submission: add only
   `submission_claimed_at` to `writing_practices`, allowing a retry to distinguish
   an active claim from an expired matching claim. No generic storage is needed.
6. Existing unique constraints plus an Agent-only expected-current-update fence
   are sufficient for durable recommendation/practice/application correctness.
   They do not promise physical exactly-once provider work after a crash; the
   contract promises at-most-once durable learning effects and bounded
   provider-backed operations per explicit turn.

## P8-02 — Core Learning Agent v1 Contract Freeze — COMPLETE

The normative contract is frozen in
[CORE_LEARNING_AGENT_POLICY.md](CORE_LEARNING_AGENT_POLICY.md). It fixes the
Writing-only version, observation order, input union, deterministic selector,
human boundaries, bounds, retry/crash semantics, public-safe trace, and the
conditional minimal migration.

## Historical implementation node definitions

The definitions below are preserved as the pre-implementation execution contract;
P8-03 through P8-13 have since been completed.

### P8-03 -- Versioned Agent Turn Schemas

- **Purpose:** Add strict versioned request, observation, response, trace, and
  stop-reason schemas.
- **Dependencies:** P8-02 and external design approval.
- **Allowed files:** focused app/schemas/ imports, schema tests, and
  policy/graph status.
- **Forbidden scope:** execution, provider behavior, persistence, web, or
  Planner/Memory policy changes.
- **Acceptance/tests:** exact closed request union; exact successful response
  union; exact no-practice reason union and five Planner-valid sequences;
  422 request-invalid, 404 learner-not-found, 404/409 safe
  ownership/lifecycle, 502/503/504 provider, and 503 persistence error
  boundaries; the exact initial_observation, ordered steps[{tool,outcome}],
  final_observation, stop_reason, current_recommendation, current_practice
  trace shape; one Outcome per tool step; submit_practice maps only to the
  existing durable result semantics submission_submitted, submission_reused,
  submission_in_progress, or submission_conflict. Internal claim-acquisition
  details are not a public outcome; no unsafe trace fields.
- **Migration permission:** no.
- **Route-back/stop:** return contract ambiguity to P8-02; stop before
  persistence.

### P8-04 -- Submission-Claim Recovery Metadata (conditional; condition met)

- **Purpose:** Add only durable metadata needed to recover an expired
  practice-submission claim.
- **Dependencies:** P8-03 and external design approval.
- **Allowed files:** WritingPractice, one Alembic revision,
  PracticeSubmissionService, focused schemas/tests, docs.
- **Forbidden scope:** generic Agent table, event sourcing, worker,
  initial-evaluation rewrite, provider API change.
- **Acceptance/tests:** add nullable submission_claimed_at; backfill every
  pre-existing in-progress NULL timestamp to explicitly expired PostgreSQL time;
  then enforce the exact generated, submission_in_progress, and submitted
  lifecycle metadata matrix with no post-upgrade legacy NULL exception. Lease
  constant is SUBMISSION_CLAIM_LEASE_SECONDS = 300; PostgreSQL time inside the
  locked claim transaction is the sole expiration/reclaim authority; expired
  matching claim gets a new token/timestamp; old token cannot finalize;
  differing fingerprint conflicts at every lease age. Upgrade tests prove
  legacy-row backfill, strict invariant, matching reclaim, and mismatch
  conflict. Downgrade removes the check before the timestamp column and retains
  all other lifecycle/claim fields.
- **Granular compatibility:** Option A is mandatory: shared
  PracticeSubmissionService lease recovery improves the existing granular
  submit endpoint after an expired matching or backfilled pre-P8 claim, while its
  request and response schemas remain unchanged and are regression-tested.
- **Migration permission:** yes -- one additive submission_claimed_at column.
- **Route-back/stop:** return another persistence need to P8-02; stop before
  observation.

### P8-05 -- Authoritative Agent Observation

- **Purpose:** Build provider-free writing-agent-observation-v1 using latest
  LearningUpdate.id DESC.
- **Dependencies:** P8-03 and P8-04 when required.
- **Allowed files:** focused Agent observation service/schema/query tests and
  imports.
- **Forbidden scope:** mutation, writing-context-v1 ordering change, Planner
  recomputation, or web.
- **Acceptance/tests:** deterministic branches, accepted-id concurrency,
  v1/v2 reconstruction, and zero provider calls. no_practice accepts exactly
  [target_achieved], [target_achieved, insufficient_evidence], [cold_start],
  [incomplete_state], or [target_unset], preserves the full sequence publicly,
  and rejects no invented sequence. The selector may receive only necessary
  internal lifecycle/application fields. Public response/trace never exposes
  claim token, claim timestamp, raw planner context, or Memory provenance.
- **Migration permission:** no.
- **Route-back/stop:** return ordering/public-data ambiguity to P8-02; stop
  before tools.

### P8-06 -- Existing-Service Tool Boundary

- **Purpose:** Adapt direct service tools and add the Agent-only two-point
  current-update generation fence.
- **Dependencies:** P8-05.
- **Allowed files:** focused Agent/tool/service modules, imports, targeted
  tests.
- **Forbidden scope:** HTTP loopback, generic tool registry, duplicated
  Planner/Memory/Evaluator/Generator logic, or granular-route changes.
- **Acceptance/tests:** preserve service ownership and no transaction across
  network work. Given observed U/R, preflight immediately before provider
  confirms U is latest and R belongs to U; stale means no provider and
  re-observation. Before persistence, the short transaction rechecks U/R;
  stale candidate is discarded with no persisted practice and re-observation.
  Granular generation semantics remain frozen.
- **Migration permission:** no.
- **Route-back/stop:** return fence ambiguity to P8-02; stop before selector.

### P8-07 -- Deterministic Action Selector

- **Purpose:** Implement the frozen observation/input action table as pure
  selection.
- **Dependencies:** P8-03, P8-05, P8-06.
- **Allowed files:** focused Agent policy/selector/schema tests.
- **Forbidden scope:** LLM routing, free-form text, direct ORM writes,
  providers, or web.
- **Acceptance/tests:** exactly one result for each valid observation/input:
  current generated practice permits first submission; matching live
  in-progress claim delegates to the claim service; matching submitted practice
  reuses persisted evaluation and completes only if unapplied; differing
  fingerprint yields submission_conflict; old generated non-current practice
  is rejected without evaluation. no_practice maps by reason_codes[0]:
  target_achieved, including its insufficient_evidence-qualified sequence,
  stops target_achieved; cold_start, incomplete_state, and target_unset stop
  no_practice. Lease time is never selected here, and only valid
  non-exceptional stops are returned.
- **Migration permission:** no.
- **Route-back/stop:** return a missing state to P8-02; stop before executor.

### P8-08 -- Bounded Agent Turn Executor

- **Purpose:** Execute selected direct-service tools, re-observe after durable
  progress, and stop within bounds.
- **Dependencies:** P8-06, P8-07.
- **Allowed files:** focused app/agent/ and service/schema tests.
- **Forbidden scope:** background autonomy, provider-spanning transaction,
  hidden reasoning storage, generic framework, or new skill.
- **Acceptance/tests:** action/observation/provider bounds; exact
  practice_submission replay after each partial durable boundary: after
  submission before completion, after completion before generation, and after
  next-practice persistence. Replay reuses evaluation, never repeats
  evaluation-provider work for submitted match, skips already-applied
  completion, and continues from current authoritative observation. Tests also
  prove one Outcome per step: an expired matching claim is reclaimed internally,
  successful provider evaluation/finalization emits submission_submitted, and
  provider/finalization failure produces the existing HTTP error with no
  successful AgentTurnResponse or duplicate durable effect.
- **Migration permission:** no beyond P8-04.
- **Route-back/stop:** return failure to owner; stop before HTTP API.

### P8-09 -- Core Agent API

- **Purpose:** Add one thin, versioned Writing Agent Turn endpoint.
- **Dependencies:** P8-08.
- **Allowed files:** route, dependency wiring, schemas, API tests, docs.
- **Forbidden scope:** granular endpoint removal, route-to-route calls, auth,
  streaming chat, browser work.
- **Acceptance/tests:** direct executor delegation; exact HTTP error boundary;
  successful responses use only public-safe trace fields.
- **Migration permission:** no.
- **Route-back/stop:** return ambiguity to P8-02; stop before UX.

### P8-10 -- Chinese-First Agent UX

- **Purpose:** Render structured Agent responses and human boundaries.
- **Dependencies:** P8-09.
- **Allowed files:** typed client, focused web components/pages/tests, docs.
- **Forbidden scope:** browser authority, free-form chat, hidden reasoning
  display, or granular-flow removal.
- **Acceptance/tests:** Chinese-first boundaries, accessible API failures,
  safe trace rendering, presentation-only cache.
- **Migration permission:** no.
- **Route-back/stop:** return unsafe/public gap to P8-02; stop before
  hardening.

### P8-11 -- Concurrency / Retry / Crash-Recovery Hardening

- **Purpose:** Prove same-learner races, stale fencing, claim recovery, retries,
  and partial success.
- **Dependencies:** P8-04, P8-08, P8-09.
- **Allowed files:** focused Agent/service/migration/API tests and owning
  repairs.
- **Forbidden scope:** broad locks, workers/queues, Planner semantic changes,
  historical rewrite.
- **Mandatory acceptance/tests:** crash after submission before completion;
  crash after completion before generation; crash after generation persistence;
  exact same practice_submission replay after each; pre-migration legacy NULL
  claim upgrades to expired/non-NULL then reclaims; live claim versus expired
  claim; different-fingerprint conflict; stale generated practice; expired
  matching reclaim is proven internally, successful finalization emits
  submission_submitted, failure emits no successful Agent response, and no
  duplicate durable effect occurs; every exact Planner-valid no_practice
  sequence;
  specifically [target_achieved, insufficient_evidence] validates, preserves
  both public reason codes, and stops target_achieved; no duplicate durable
  effects and no stale practice persistence.
- **Migration permission:** corrective P8-04-only.
- **Route-back/stop:** return defects to owner; stop before compatibility
  validation.

### P8-12 -- Lifecycle Compatibility + E2E / CI

- **Purpose:** Preserve granular lifecycle behavior and validate bounded Agent
  path.
- **Dependencies:** P8-10, P8-11.
- **Allowed files:** focused tests/E2E/CI only for demonstrated issues, owning
  repairs, docs.
- **Forbidden scope:** feature expansion, policy changes to satisfy tests, new
  IELTS skills.
- **Acceptance/tests:** granular APIs including Option A lease recovery, v1/v2
  recommendations, Agent branches/retries, and Chromium pass.
- **Migration permission:** no.
- **Route-back/stop:** return defects to owner; stop after clean evidence.

### P8-13 -- Internal Final Audit

- **Purpose:** Reconcile code, migration, policy, graph, API, UX, tests, and
  phase boundaries.
- **Dependencies:** P8-12.
- **Allowed files:** audit/status docs and minimal documentation fixes.
- **Forbidden scope:** new features, Phase 9, unreviewed scope.
- **Acceptance/tests:** fresh evidence, exact inventory, crash/retry/lease
  proof, compatibility, exclusions.
- **Migration permission:** no.
- **Route-back/stop:** route defects to owner; otherwise stop for external
  implementation review.


## Current Phase 8 status

```text
Phase 1 = COMPLETE
Phase 2 = COMPLETE
Phase 3 = COMPLETE
Phase 4 = COMPLETE
Phase 5 = COMPLETE
Phase 6 = COMPLETE
Phase 7 = COMPLETE

P8-01 = COMPLETE
P8-02 = COMPLETE
P8-03 = COMPLETE
P8-04 = COMPLETE
P8-05 = COMPLETE
P8-06 = COMPLETE
P8-07 = COMPLETE
P8-08 = COMPLETE
P8-09 = COMPLETE
P8-10 = COMPLETE
P8-11 = COMPLETE
P8-12 = COMPLETE
P8-13 = INTERNAL_AUDIT_COMPLETE
Phase 8 = INTERNAL_AUDIT_COMPLETE
External Design Review = APPROVED
External Implementation Review = PENDING
Phase 9 = NOT_STARTED
```

## Historical design-run exclusions

Historical design-run exclusions: the completed implementation remains limited to
the authorized Phase 8 scope and introduces no additional dependency, Docker, or
configuration change; no LangChain,
LangGraph, multi-agent runtime, LLM router/planner, RAG/vector database,
background execution, authentication, payments, or Reading/Listening/Speaking
capability was authorized. Phase 8 now stops for External Implementation Review.