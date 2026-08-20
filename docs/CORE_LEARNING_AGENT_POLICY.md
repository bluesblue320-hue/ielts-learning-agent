# Core Learning Agent Policy

## Contract status

**Frozen Phase 8 P8-02 design contract, repaired after external design review.**
This document defines the intended writing-core-learning-agent-v1 behavior. It
does not authorize implementation: P8-03 and later require external design
approval, and no Agent runtime, API, migration, test, or web behavior exists
because of this document.

- Repository: bluesblue320-hue/ielts-learning-agent
- Branch: phase/8-core-learning-agent-v1
- Base master: 495022ecb806c35e53c9e3cdfc09c5dfcf024e72
- Agent version: writing-core-learning-agent-v1
- Scope: one explicitly invoked, bounded, Writing-only Agent Turn

## 1. Responsibility and boundaries

The Core Learning Agent decides when and which existing operation may execute in
one explicit turn. It observes authoritative learner-owned state, selects
deterministically, calls application/domain services directly, re-observes after
durable progress, and stops at human, wait, terminal, error, or bound
boundaries.

The persisted Planner decision continues to own target skill, target band,
reason codes, planner version, and Phase 7 exact-tie Memory behavior. The Agent
must not recompute or alter a plan, inject Memory context, or pass Memory to a
generator. It is not a chat agent, LLM router/planner, ReAct loop, multi-agent
system, generic tool registry, background worker, or autonomous scheduler. It
does not call FastAPI routes or browser APIs.

## 2. Authoritative observation

### 2.1 New observation contract

P8-05 must add provider-free, read-only writing-agent-observation-v1. It is
separate from, and must not mutate, writing-context-v1.

For a known learner it reads:

1. learner existence and four-skill materialized state;
2. the latest learner-owned LearningUpdate ordered exactly by
   LearningUpdate.id DESC, limited to one;
3. that update's PracticeRecommendation through the existing versioned public
   reconstruction path;
4. the optional WritingPractice linked to that recommendation; and
5. its lifecycle/evaluation-application relationship when needed.

The current recommendation is owned by the largest accepted LearningUpdate.id,
not the largest timestamp. This is Phase 7 accepted-update chronology. The
observation may expose existing public recommendation/practice forms only; it
must not expose a raw planner context snapshot, Memory provenance, claim token,
or claim timestamp.

### 2.2 Frozen writing-context-v1 boundary

app/memory/context.py remains the Phase 6 resume contract. Its created_at DESC,
id DESC ordering, version, endpoint, and browser behavior are frozen. The Agent
does not use it as authoritative observation. The P8 observation supplies the
accepted-order view without changing context v1.

### 2.3 Exact observation enum

The observation kind is exactly one of:

- needs_initial_writing: no learner-owned LearningUpdate;
- no_practice: latest recommendation is no_practice, including its safe
  persisted reason-code list;
- needs_generation: current recommendation has no WritingPractice;
- needs_practice_submission: current practice is generated;
- await_submission: current practice is submission_in_progress; or
- needs_completion: current practice is submitted and its evaluation has no
  applied LearningUpdate.

The Agent-safe no_practice reason-code enum is exactly target_achieved,
insufficient_evidence, cold_start, incomplete_state, or target_unset. The only
accepted ordered sequences are the Planner-valid sequences:

- [target_achieved]
- [target_achieved, insufficient_evidence]
- [cold_start]
- [incomplete_state]
- [target_unset]

The Agent preserves the full persisted sequence in its public response. Stop
mapping uses the primary reason at reason_codes[0]: target_achieved maps to the
target_achieved stop, while cold_start, incomplete_state, and target_unset map
to no_practice. Therefore [target_achieved, insufficient_evidence] also stops
target_achieved; insufficient_evidence is a qualifier, not another terminal
state. The Agent must neither invent a sequence nor present the other primary
reasons as target achievement.

An impossible persisted shape is an API/service error, never a guessed
continuation or successful Agent stop. Observation makes no provider call and
writes no row.

## 3. Agent Turn input and API

The only future public surface is:

    POST /learners/{learner_id}/writing/agent/turn

It follows existing learner-scoped Writing route conventions. Its request is a
strict discriminated union; unknown fields are rejected.

    continue
      { "turn_type": "continue" }

    practice_submission
      {
        "turn_type": "practice_submission",
        "practice_id": positive integer,
        "essay": validated Writing essay text
      }

There is no free-form natural-language field, target override, Planner version
selector, provider selector, route name, raw question, or initial Writing essay.

### Initial Writing exclusion

Initial Writing is outside Agent Turn v1. The existing POST /writing/evaluate
then POST /learners/{learner_id}/writing/evaluations/{evaluation_id}/apply
bootstrap remains unchanged. A pre-apply evaluation is not learner-owned and
has no durable learner-scoped input identity. Initial question/essay in an Agent
request is invalid and makes no provider call.

## 4. Direct service tools and generation fence

The executor may call only these direct boundaries:

| Tool enum | Boundary | Authority preserved |
| --- | --- | --- |
| observe | P8-05 Agent observation | persisted learner-owned state |
| generate_practice | PracticeGenerationService.generate_or_resolve(), through the Agent-only P8-06 fence | persisted recommendation owns target and generator input |
| submit_practice | PracticeSubmissionService.submit() | persisted practice owns the question; client provides essay only |
| complete_practice | PracticeCompletionService.complete() | existing idempotent apply owns rebuild/replan |

WritingEvaluationService is internal to PracticeSubmissionService. The Agent
does not call it separately. Evaluation persistence and apply remain internals
of the allowed service flows.

For an Agent generation selected from observed update U and recommendation R,
P8-06 must use this exact two-point freshness fence:

1. Immediately before provider work, verify that U is still the learner's latest
   accepted LearningUpdate.id and that R belongs to U. If stale, call no
   provider and re-observe.
2. Provider work occurs outside any database transaction.
3. After the provider returns, before an insert/resolve and inside the short
   persistence boundary, re-check that U is current and R belongs to it. If
   stale, discard the candidate, persist nothing, and re-observe.

The granular generation endpoint keeps its existing behavior. It does not
silently receive this Agent-only fence.

## 5. Deterministic selection and exact practice-submission replay

The selector never calculates lease expiry. For every practice_submission it
first resolves the learner-owned practice using this durable identity:

    learner_id + practice_id + authoritative persisted question + essay fingerprint

The practice row, not a request cache or generic Agent table, owns replay.

| Referenced practice | Required action | Required result |
| --- | --- | --- |
| Current generated practice | submit_practice, then normal completion flow | first submission allowed |
| submission_in_progress with matching fingerprint | submit_practice delegates claim decision under row lock | live claim waits; expired claim may resume |
| submitted with matching fingerprint | submit_practice returns reused persisted evaluation, without evaluation-provider work | complete only if unapplied; otherwise skip; then re-observe current state |
| submitted with different fingerprint | no provider or mutation | submission_conflict |
| generated but no longer current | no provider or mutation | safe HTTP 409 stale practice state |
| missing or another learner's practice | no provider or mutation | existing safe HTTP 404 or 409 |

A submitted matching practice remains replayable even if another recommendation
or practice is now current. A stale unsubmitted generated practice is never
evaluated.

The normal selector table is:

| Observation | Valid input | Action order | Successful stop |
| --- | --- | --- | --- |
| needs_initial_writing | continue | none | needs_initial_writing |
| no_practice with primary reason target_achieved, for either Planner-valid sequence | continue | none | target_achieved |
| no_practice with primary reason cold_start, incomplete_state, or target_unset | continue | none | no_practice |
| needs_generation | continue | generate_practice, observe | practice_ready, target_achieved, or no_practice |
| needs_practice_submission | continue | none | needs_practice_submission |
| await_submission | continue | none | await_submission |
| needs_completion | continue | complete_practice, observe, generate_practice only if needed, observe | practice_ready, target_achieved, or no_practice |
| needs_practice_submission | matching current generated practice_submission | submit_practice, complete_practice, observe, generate_practice only if needed, observe | practice_ready, target_achieved, or no_practice |
| await_submission | matching in-progress practice_submission | submit_practice delegates live/expired claim outcome | await_submission or normal resulting stop |
| any current observation | matching submitted practice_submission retry | submit_practice reuses evaluation, complete only if unapplied, observe, continue from current state within bounds | resulting valid stop |

A submitted replay after completion is not rejected merely because a later
practice is current. If its evaluation is applied, completion is skipped, the
current authoritative observation is read, and selection continues. This makes
an exact HTTP retry safe after a crash after submission, after completion, or
after completion plus next-practice persistence.

Submitted, reused, or reclaimed then follows the replay rule. A live claim produces
await_submission; a different fingerprint produces submission_conflict. The
Agent never submits without an essay, never generates after no_practice, and
does no work after a terminal, human, wait, API-error, or bound boundary.

The normal first-submission flow is:

    submit/evaluate -> complete/apply/replan -> generate once only if needed
    -> stop for the next essay

No generic Agent idempotency record or background autonomy is permitted.

## 6. Bounds and transactions

One turn has these hard limits:

- maximum mutating service-tool executions: 3;
- maximum observations: 4, including initial and post-durable observations;
- maximum provider-backed service invocations: 2, one evaluation and one
  next-practice generation;
- maximum automatic generations: 1; and
- maximum automatic completions: 1.

A reused submission is provider-free and a skipped completion is not an
execution. The Agent counts service invocations, not internal retries already
owned by RetryingProvider or RetryingPracticeGenerator.

No Agent transaction spans provider/network work. Observations and durable
service transactions are short. The executor keeps no learner/practice lock or
ORM transaction while awaiting a provider. If a bound is reached before a valid
classification, it returns successful max_actions and schedules nothing.

## 7. HTTP error boundary and exact public trace

Invalid request schema, unknown union member, or unknown field uses existing
422 request_invalid. Missing learner uses existing 404 learner_not_found.
Missing/cross-owner practice and invalid persisted ownership/lifecycle use
existing safe 404 or 409 as appropriate. A stale generated practice is 409 and
never calls a provider.

Provider failures preserve existing 502, 503, or 504 mapping. Persistence and
database failures preserve 503 mapping. Impossible persisted shapes use this
safe API-error path. Agent code must not convert an exception into HTTP 200.

The successful stop-reason enum is exactly:

    needs_initial_writing
    needs_practice_submission
    practice_ready
    await_submission
    target_achieved
    no_practice
    submission_conflict
    max_actions

The stop union has no catch-all failure or invalid-input success member; stops are valid, non-exceptional turn states.

Every successful AgentTurnResponse contains exactly this response-only safe
trace:

    {
      agent_version: "writing-core-learning-agent-v1",
      initial_observation: {
        kind: ObservationKind,
        no_practice_reason_codes: NoPracticeReason[] | null
      },
      steps: [{ tool: Tool, outcome: Outcome }],
      final_observation: {
        kind: ObservationKind,
        no_practice_reason_codes: NoPracticeReason[] | null
      },
      stop_reason: StopReason,
      current_recommendation: PublicPracticeRecommendation | null,
      current_practice: PublicWritingPractice | null
    }

ObservationKind is exactly Section 2.3. NoPracticeReason is exactly
target_achieved, insufficient_evidence, cold_start, incomplete_state, or
target_unset. Tool is exactly
observe, generate_practice, submit_practice, or complete_practice. Outcome is
exactly one of:

    observation_classified
    practice_generated
    practice_resolved
    generation_stale_discarded
    submission_submitted
    submission_reused
    submission_in_progress
    submission_reclaimed
    submission_conflict
    completion_applied
    completion_reused

Each tool step emits exactly one Outcome. The submit_practice mapping is exact:

- a new generated submission that finalizes successfully emits
  submission_submitted;
- an already submitted matching replay emits submission_reused;
- a matching live claim emits submission_in_progress;
- an expired matching claim that is atomically reclaimed, evaluated through the
  provider, and successfully finalized as submitted in that same tool invocation
  emits submission_reclaimed; and
- a different fingerprint emits submission_conflict.

A reclaimed invocation never also emits submission_submitted. If reclaim occurs
but provider evaluation or finalization fails, no successful AgentTurnResponse
and no successful submission_reclaimed outcome is produced; the existing safe
HTTP provider or persistence error applies.

The trace contains no chain-of-thought, reasoning prose, provider reasoning, raw
prompts/payloads, raw planner context snapshot, selection trace, Memory
provenance, claim token, claim timestamp, database error, or exception text. It
is not a persistent Agent-run log.

## 8. Idempotency, claim lease, and recovery

### 8.1 Durable ownership

No generic Agent Turn table or idempotency ledger is permitted. Durable
ownership is:

- recommendation id for generation;
- learner id, practice id, authoritative question, and essay fingerprint for
  submission;
- evaluation id for apply/completion; and
- latest accepted update id for Agent-generation freshness.

This provides at-most-once durable practice, attempt/evaluation, LearningUpdate,
evidence, state, and recommendation effects. It cannot promise physical
exactly-once provider work after process crash because providers have no durable
idempotency receipt. That is a provider-cost limitation only.

### 8.2 P8-04 migration, strict metadata invariant, and lease authority

Before Agent Turn accepts practice_submission, P8-04 performs this exact
migration sequence:

1. add nullable submission_claimed_at TIMESTAMPTZ to writing_practices;
2. detect every pre-existing submission_in_progress row whose
   submission_claimed_at is NULL;
3. backfill each such row with an explicitly expired PostgreSQL timestamp,
   CURRENT_TIMESTAMP - INTERVAL '301 seconds', so the next explicit matching
   retry can reclaim it; and
4. only after that backfill, enforce the strict lifecycle metadata invariant
   below through model validation and a database check constraint.

SUBMISSION_CLAIM_LEASE_SECONDS is exactly 300. After upgrade there is no
permanent legacy NULL exception state. No generic Agent storage is allowed.

| Lifecycle | submission_fingerprint | claim_token | submission_claimed_at | attempt_id |
| --- | --- | --- | --- | --- |
| generated | NULL | NULL | NULL | NULL |
| submission_in_progress | NOT NULL | NOT NULL | NOT NULL | NULL |
| submitted | NOT NULL | NULL | NULL | NOT NULL |

PracticeSubmissionService owns lease checking and reclamation under the locked
WritingPractice row. PostgreSQL database time inside that claim transaction is
the sole lease-expiration authority. Python datetime.now(), browser time,
selector wall clock, and other application clocks have no expiry authority.

For an explicit matching submission against submission_in_progress:

- an unexpired claim returns in_progress and calls no provider;
- an expired matching claim atomically gets a new opaque token and new
  submission_claimed_at before provider work;
- old tokens can never finalize;
- a different fingerprint returns submission_conflict at every lease age; and
- no timer, worker, or background reclamation exists.

P8-04 migration tests must seed a pre-migration submission_in_progress row,
prove upgrade succeeds, prove its timestamp is expired and non-NULL, prove the
strict final invariant holds, prove a matching explicit retry can reclaim, and
prove a different fingerprint still conflicts.

Downgrade removes the lifecycle check constraint before dropping
submission_claimed_at. It does not rewrite lifecycle_state,
submission_fingerprint, claim_token, or attempt_id; an in-progress row therefore
returns to the pre-P8 schema's indefinite in_progress behavior after the
timestamp column is removed.

### 8.3 Granular compatibility: Option A

Option A is frozen. Lease recovery is a domain-level
PracticeSubmissionService improvement shared with existing granular
POST /learners/{learner_id}/writing/practices/{practice_id}/submit.

Granular submit request/response schemas do not change. Its behavior is
explicitly improved for an expired matching claim, including a pre-P8 claim
made expired by migration backfill: it can reclaim and continue instead of
remaining indefinitely in_progress. Live matching claims still return
in_progress and differing fingerprints still conflict. P8-04 must document and
regression-test this behavior.

### 8.4 Replay after every partial durable boundary

The identical practice_submission request is replay-safe:

1. After submission finalizes but before completion: reuse persisted evaluation
   with no evaluation-provider call, then complete once.
2. After completion commits but before generation: reuse evaluation, detect
   application, skip completion, re-observe current recommendation, then
   generate once only if needed.
3. After next-practice persistence: reuse old evaluation, skip completion,
   re-observe current generated practice, stop needs_practice_submission, and
   do not generate another practice.

For an expired matching claim, submission_reclaimed is the one successful
submit_practice outcome only when that invocation reclaims, performs provider
evaluation, and finalizes submitted. If provider work or finalization fails,
existing owned-claim release and safe HTTP mapping apply; no successful Agent
response is emitted, and a later explicit retry may call the provider. These
cases never create duplicate durable attempts, evaluations, LearningUpdates, or
recommendations.

## 9. Concurrency

There is no global Agent lock or generic Agent lease. Existing narrow ownership
remains authoritative:

- apply_writing_evaluation() serializes same-learner application with learner
  lock and evaluation uniqueness;
- PracticeSubmissionService serializes one practice with row lock, fingerprint,
  token, and P8-04 timestamp; and
- recommendation uniqueness selects one durable generated practice.

Concurrent matching submissions yield one live claim; followers await without an
evaluation provider call. After expiry, one locked claimant gets the new token;
an old token cannot finalize. Concurrent completions reuse the applied update.
Submitted retries are anchored to their practice even after current state moves;
stale unsubmitted generated practices are not.

P8 adds only the two-point Agent generation fence and per-practice timestamp.
Concurrent generation may have provider-cost races but only one durable practice
wins. A stale candidate is discarded before persistence and re-observed. The
response always reflects fresh server state, not browser cache.

## 10. Compatibility, Memory, generator, and browser boundaries

Both writing-practice-gap-v1 and writing-practice-gap-memory-v2
recommendations are actionable. The Agent uses their existing public
reconstruction/generation/submission/completion/history/progress/resume paths;
v1 requires no v2 trace.

Memory remains Planner v2 exact-maximum-gap-tie-only. The Agent never reads a
planner context snapshot or supplies Memory to the generator. The generator
uses persisted recommendation authority and still rejects target mismatch.

Granular endpoints and browser flows remain supported. P8-10 may add typed
agentTurn and Chinese-first rendering, but may not make browser cache
authoritative, persist traces in the browser, or remove granular lifecycle
controls. PostgreSQL remains authoritative.

## 11. Normative examples

| Case | State/input | Required result |
| --- | --- | --- |
| Fresh learner | continue; no LearningUpdate | needs_initial_writing, no provider/write. |
| Needs generation | continue; current recommendation has no practice | two-point-fenced generation once, then practice_ready. |
| Generated practice | continue; current practice generated | needs_practice_submission, no provider. |
| Submitted practice | continue; current submitted evaluation unapplied | complete, re-observe, maybe generate; practice_ready, target_achieved, or no_practice. |
| First essay | matching current generated practice_submission | submit/evaluate, complete/replan, maybe generate, then next essay boundary. |
| no_practice truth | continue; latest no_practice | Preserve exactly one of the five Planner-valid sequences; primary target_achieved, including [target_achieved, insufficient_evidence], stops target_achieved; other primary reasons stop no_practice. |
| Provider/persistence failure | service/provider fails | preserve 502/503/504 or 503, never an HTTP 200 failure stop. |
| Exact retry | identical practice_submission after submission, completion, or next-practice persistence | reuse evaluation, apply at most once, re-observe current state, no duplicate durable effect. |
| Claim recovery | matching live or expired claim, including a pre-P8 row backfilled expired during upgrade | live awaits/no provider; expired matching retry reclaims; differing essay conflicts; old token cannot finalize; final in-progress timestamps are non-NULL. |
| Stale generated practice | old generated practice_submission | safe HTTP 409, no mutation/provider. |

## 12. Future implementation inventory

P8-03 and later may touch focused owning files only: app/schemas/agent.py,
app/agent observation/selector/executor modules, practice claim model and
P8-04 Alembic revision, generation/submission services, Agent route/dependency
composition, typed web client/UI, and focused backend/API/concurrency/E2E tests.
This is planning only; none is changed or authorized by this design run.

## 13. Frozen exclusions

No LangChain, LangGraph, generic Agent framework, multi-agent runtime, LLM
router/planner, RAG, vector store, Redis, queue, worker, background task,
authentication, payment, new IELTS skill, Reading, Listening, Speaking, or
Phase 9 work belongs to Agent v1. External design review must approve this
contract before P8-03 starts.
