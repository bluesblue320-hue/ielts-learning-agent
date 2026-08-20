# Core Learning Agent Policy

## Contract status

**Frozen design contract for Phase 8 P8-02.** This policy defines the intended
`writing-core-learning-agent-v1` behavior only. It is not implementation
authority. P8-03 and later require external design review; no Agent runtime,
API, migration, test, or web behavior exists because of this document.

- **Repository:** `bluesblue320-hue/ielts-learning-agent`
- **Design branch:** `phase/8-core-learning-agent-v1`
- **Base master:** `495022ecb806c35e53c9e3cdfc09c5dfcf024e72`
- **Agent version:** `writing-core-learning-agent-v1`
- **Scope:** one explicitly invoked, bounded, Writing-only Agent Turn

## 1. Responsibility and boundaries

The Core Learning Agent decides **when and which existing operation may execute
inside one explicit turn**. It observes authoritative learner-owned state,
selects deterministically, calls an existing service directly, re-observes after
durable progress, and stops at a human, wait, terminal, safety, or bound
boundary.

It does not decide what IELTS skill to train. The persisted Planner decision
continues to own `target_skill`, target band, reason codes, planner version, and
Phase 7 exact-tie Memory behavior. The Agent must never recompute a plan, alter
a Planner decision, inject Memory context, or pass Memory data to a generator.

It is not a chat agent, LLM router, LLM planner, ReAct loop, multi-agent system,
generic tool registry, background worker, or autonomous scheduler. It does not
call FastAPI routes or browser APIs. It calls application/domain services
in-process through explicit dependencies.

## 2. Authoritative observation

### 2.1 New observation contract

P8-05 must add a provider-free, read-only `writing-agent-observation-v1`.
It is distinct from and must not mutate `writing-context-v1`.

For a known learner, the observation reads:

1. learner existence and current four-skill materialized state;
2. latest learner-owned `LearningUpdate`, ordered exactly by
   `LearningUpdate.id DESC` and limited to one;
3. that update's one `PracticeRecommendation`, reconstructed through the
   existing versioned public reconstruction path;
4. the one optional `WritingPractice` linked to that recommendation; and
5. its lifecycle/evaluation-application relationship where needed to classify a
   stop or direct-service action.

The current recommendation is therefore the recommendation owned by the
largest accepted `LearningUpdate.id`, not the largest timestamp. This matches
Phase 7 accepted-update chronology. The observation is allowed to expose the
same public recommendation/practice data already exposed by existing APIs, but
not the raw planner context snapshot or Memory provenance ids.

### 2.2 Frozen `writing-context-v1` boundary

`app/memory/context.py` remains the Phase 6 resume contract. Its
`created_at DESC, id DESC` ordering, response version, endpoint, and browser
behavior are frozen. The Agent must not call it as its authoritative observation
and must not silently change it. The separate P8 observation solves the
accepted-order requirement without changing existing context semantics.

### 2.3 Observation classifications

The Agent observation classifies exactly one of:

- `needs_initial_writing`: no learner-owned `LearningUpdate`;
- `target_achieved`: latest recommendation is `no_practice`;
- `needs_generation`: latest practice recommendation has no `WritingPractice`;
- `needs_practice_submission`: its relevant practice is `generated`;
- `await_submission`: its relevant practice is `submission_in_progress`;
- `needs_completion`: its relevant practice is `submitted` and its evaluation
  has no applied `LearningUpdate`.

An impossible persisted shape is a safe internal failure, never a guessed
continuation. The observation does not make a provider call or write rows.

## 3. Agent Turn input and API

The only future public surface is:

```text
POST /learners/{learner_id}/writing/agent/turn
```

It follows existing learner-scoped Writing route conventions. Its request is a
strict discriminated union; unknown fields are rejected.

```text
continue
  { "turn_type": "continue" }

practice_submission
  {
    "turn_type": "practice_submission",
    "practice_id": positive integer,
    "essay": validated Writing essay text
  }
```

There is no free-form natural-language field, desired-skill field, Planner
version selector, target override, provider selector, route name, raw question,
or initial Writing essay in this union.

### Initial Writing exclusion

Initial Writing is a bootstrap action outside Agent Turn v1. The existing
`POST /writing/evaluate` followed by
`POST /learners/{learner_id}/writing/evaluations/{evaluation_id}/apply` remains
supported and unchanged. The exclusion is mandatory because a persisted but
unapplied evaluation is not learner-owned and the same question/essay has no
durable idempotency identity. An Agent v1 request containing initial question
and essay is invalid input and makes no provider call.

## 4. Direct service tools

The executor may call only these existing or P8-specific direct boundaries:

| Tool enum | Direct boundary | Authority preserved |
| --- | --- | --- |
| `observe` | P8-05 Agent observation | persisted learner-owned state only |
| `generate_practice` | `PracticeGenerationService.generate_or_resolve()` through the P8-06 current-update fence | persisted Planner recommendation owns target and generator input |
| `submit_practice` | `PracticeSubmissionService.submit()` | persisted practice owns question; client supplies essay only |
| `complete_practice` | `PracticeCompletionService.complete()` | existing idempotent apply owns state rebuild and replanning |

`WritingEvaluationService` remains internal to `PracticeSubmissionService`; the
Agent does not call it as a separate tool. `WritingEvaluationPersistenceService`
and `apply_writing_evaluation()` remain service internals for these allowed
flows. Generation and submission retain their existing provider boundaries.

P8-06 must add an Agent-only expected-current-update fence around generation:
the observed `LearningUpdate.id` and recommendation id are revalidated before
persisting generated content. If another accepted update is now latest, the
candidate content is discarded, no obsolete practice is persisted, and the turn
re-observes. Existing granular generation retains its current behavior.

## 5. Deterministic action-selection table

| Observed state | Valid input | Selected action(s), in order | Stop reason |
| --- | --- | --- | --- |
| `needs_initial_writing` | `continue` | none | `needs_initial_writing` |
| `target_achieved` | `continue` | none | `target_achieved` |
| `needs_generation` | `continue` | generate → observe | `practice_ready` or `target_achieved` |
| `needs_practice_submission` | `continue` | none | `needs_practice_submission` |
| `await_submission` | `continue` | none | `await_submission` |
| `needs_completion` | `continue` | complete → observe → generate only when needed → observe | `practice_ready` or `target_achieved` |
| `needs_practice_submission` | matching `practice_submission` | submit → complete → observe → generate only when needed → observe | `practice_ready` or `target_achieved` |
| `await_submission` | matching `practice_submission` | none while an unexpired claim exists | `await_submission` |
| any state | nonmatching practice id, unsupported union member, or impossible lifecycle | none | `invalid_turn_input` or `safe_failure` |

A submission result of `submitted` or `reused` proceeds to completion. A
`conflict` result stops with `submission_conflict`; `in_progress` stops with
`await_submission`. The selector never submits without an essay, never
generates after `target_achieved`, and never executes work after a terminal or
human boundary.

The permitted behavior is therefore:

```text
user submits practice essay in one explicit Agent Turn
-> submit/evaluate
-> complete/apply/replan
-> generate next practice if the new persisted recommendation needs one
-> stop and request the next essay
```

This composes the existing services and their durable boundaries; it does not
change the independent granular API semantics or create background autonomy.

## 6. Bounds and transaction model

A single explicit Agent Turn has these hard limits:

- **maximum mutating service-tool executions:** 3;
- **maximum observations:** 4 (initial observation plus one after each action);
- **maximum provider-backed service invocations:** 2 (one practice evaluation
  and one next-practice generation);
- **maximum automatic generations:** 1; and
- **maximum automatic completions:** 1.

The Agent counts service invocations, not internal retry attempts already owned
by the configured `RetryingProvider` or `RetryingPracticeGenerator`. It must not
increase, configure, or loop those provider retries.

No Agent Turn holds one database transaction across a provider/network call.
Observations are short provider-free reads; each existing service keeps its own
short transaction/claim/finalization boundary. The executor re-observes only
after a service returns a durable or classified result. It never keeps a learner
lock, practice lock, or ORM transaction open while awaiting a provider.

If a bound is reached before a valid classification, the Agent stops with
`max_actions`; no hidden continuation is scheduled.

## 7. Stop reasons and public-safe trace

The frozen public stop-reason union is:

```text
needs_initial_writing
needs_practice_submission
practice_ready
await_submission
target_achieved
submission_conflict
invalid_turn_input
safe_failure
max_actions
```

The response includes only a public-safe trace:

```text
agent_version
observed_action
executed_tools: ordered enum list
outcomes: ordered public enum list
stop_reason
current public recommendation and/or practice when needed for the next UX step
```

It must not expose chain-of-thought, provider reasoning, prompts, raw provider
payloads, raw planner context snapshots, selection traces, Memory provenance
ids, claim tokens, lease details, database constraint names, or exception text.
The trace is response-only and is not a new persistent run log.

## 8. Idempotency, persistence, retry, and crash recovery

### 8.1 Ownership decision

No generic Agent Turn table or idempotency ledger is permitted. For the limited
input union, idempotency belongs to the durable domain entity:

- recommendation id uniquely owns generation;
- practice id plus authoritative question/essay fingerprint owns submission;
- evaluation id uniquely owns apply/completion; and
- latest accepted update id fences Agent generation freshness.

This guarantees at-most-once durable practice, attempt/evaluation,
LearningUpdate, evidence, state, and recommendation effects. It cannot promise
physical exactly-once provider invocation after a process crash because the
existing providers do not expose a durable idempotency receipt. This limitation
must be documented and tested as a provider-cost, not learner-state, boundary.

### 8.2 Required conditional P8-04 migration

Before Agent Turn v1 accepts `practice_submission`, P8-04 must add one nullable
`submission_claimed_at TIMESTAMPTZ` column to `writing_practices`, with model,
migration, and lifecycle validation updates. It is non-null only while
`lifecycle_state = submission_in_progress` and is cleared on finalization or
owned claim reset.

The frozen claim lease is **300 seconds**. On an explicitly invoked retry:

- an unexpired matching claim returns `await_submission` and does not call a
  provider;
- a different fingerprint remains `submission_conflict`;
- an expired matching claim is atomically reclaimed under the existing practice
  row lock with a new token and timestamp;
- an obsolete token can never finalize; and
- there is no timer, worker, or background reclamation.

A reclaim after an actual process crash may repeat provider work, but it cannot
create more than one durable attempt/evaluation or learning application. This is
the smallest justified recovery storage because current `updated_at` is not a
claim timestamp and current rows cannot distinguish a live claim from an
abandoned one.

### 8.3 Partial success

If completion commits and the subsequent generator fails, the Agent returns
`safe_failure` without rolling back completion. The next explicit `continue`
observes the committed latest recommendation, calls idempotent generation, and
returns `practice_ready` or `target_achieved`.

If submission finalizes before the executor crashes, the next matching turn gets
`reused`, completion safely reuses apply, and the Agent continues within normal
bounds. If a claim is still active, the lease rules above govern a later retry.

## 9. Concurrency

There is no global Agent-level lock or generic Agent lease. Existing narrow
locks and uniqueness constraints remain authoritative:

- `apply_writing_evaluation()` serializes same-learner application with the
  learner row lock and evaluation uniqueness;
- practice submission serializes one practice with its existing row lock and
  claim; and
- practice generation has one durable winner by recommendation uniqueness.

P8 adds only the expected-current-update fence for Agent generation and the
conditional per-practice claim timestamp. Concurrent Agent Turns may each reach
a provider-backed generation operation for the same recommendation, but only one
durable practice can result; no global lease is justified for provider-cost
optimization. A stale Agent generation must not persist after a newer accepted
update; it re-observes instead.

Concurrent Agent submissions of one practice yield one active claim; followers
return `await_submission`. Concurrent completions reuse the existing applied
update. The response always reflects a fresh observation after the turn's own
durable operation, rather than browser cache state.

## 10. Compatibility, Memory, generator, and browser boundaries

Both `writing-practice-gap-v1` and `writing-practice-gap-memory-v2`
recommendations are actionable. The Agent reconstructs their existing public
forms, does not require a v2 trace for v1, and uses the same generation,
submission, completion, history, progress, and resume data paths already tested.

Memory informs only Planner v2's existing exact-tie decision. The Agent neither
queries a planner context snapshot nor supplies Memory to the generator. The
generator receives the persisted recommendation's approved public authority and
must continue to reject a returned target mismatch.

The existing granular endpoints and browser flows remain supported. P8-10 may
add a typed `agentTurn` API-client call and focused Chinese-first rendering, but
must not treat browser cache as state, store agent traces durably in the browser,
or remove evaluate/apply/generate/submit/complete controls. PostgreSQL remains
authoritative; refresh/reload re-observes the server.

## 11. Normative examples

| Case | Input and persisted state | Required result |
| --- | --- | --- |
| A. Fresh learner | `continue`; no `LearningUpdate` | no provider/tool write; `needs_initial_writing`. |
| B. Recommendation needs generation | `continue`; latest accepted recommendation has no practice | generate once through current-update fence; return public practice and `practice_ready`. |
| C. Generated practice | `continue`; current practice is `generated` | no provider call; `needs_practice_submission`. |
| D. Submitted practice | `continue`; current practice is `submitted` with unapplied evaluation | complete, re-observe, maybe generate once; stop at `practice_ready` or `target_achieved`. |
| E. Practice essay flow | matching `practice_submission`; current practice is generated | submit/evaluate, complete/replan, maybe generate; stop for the next essay. |
| F. Target achieved | `continue`; latest recommendation is `no_practice` | no provider/tool write; `target_achieved`. |
| G. Generation failure after completion | completion has committed; next generator fails | return `safe_failure`; later `continue` resumes from persisted recommendation without re-completing. |
| H. Repeated identical turn | same essay after durable submission/finalization | submission returns `reused`, completion reuses apply, and durable rows are not duplicated. |
| I. Concurrent turns | two turns see the same current recommendation/practice | uniqueness/claim yields one durable practice or active submission; stale generation re-observes. |
| J. `submission_in_progress` recovery | matching retry while claim is live or expired | live claim returns `await_submission`; after P8-04, expired matching claim reclaims under lock and resumes without duplicate durable effects. |

## 12. Future implementation inventory

P8-03+ will likely touch only focused new/owning files: `app/schemas/agent.py`,
`app/agent/` observation/selector/executor modules, the practice claim model and
P8-04 Alembic revision, the generation and submission services, an Agent route
and dependency composition, the typed web API client and focused Chinese-first
UI, backend schema/service/API/concurrency tests, and Agent browser E2E. This
inventory is planning only; none of these files is changed or authorized now.

## 13. Frozen exclusions

No LangChain, LangGraph, generic Agent framework, multi-agent runtime, LLM
router/planner, RAG, vector store, Redis, queue, worker, background task,
authentication, payment, new IELTS skill, Reading, Listening, Speaking, or Phase
9 work belongs to Agent v1. External design review must approve this contract
before P8-03 starts.