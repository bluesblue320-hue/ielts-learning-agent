# Web Product Contract — Phase 5

**Version:** `phase5-web-product-mvp-v1`
**Status:** FROZEN by P5-02 (design only)
**Audience:** the future P5-03 through P5-15 implementation and test work

This document is the browser-product contract for the existing Phase 2–4
backend. It does not change their policies or authorize their modification.
The frontend is a presentation client; FastAPI remains the sole application and
domain layer, and PostgreSQL remains the source of truth.

## 1. Chinese-first language and content policy

The default learner-facing UI is Simplified Chinese (`zh-CN`). Use Chinese for
navigation, buttons, loading and error states, learning explanations,
dashboard/form labels, and training UI. Use these criterion labels:

| Backend concept (never learner-facing) | Learner-facing label |
| --- | --- |
| `task_response` | 任务回应（Task Response） |
| `coherence_and_cohesion` | 连贯与衔接（Coherence and Cohesion） |
| `lexical_resource` | 词汇资源（Lexical Resource） |
| `grammatical_range_and_accuracy` | 语法多样性与准确性（Grammatical Range and Accuracy） |

Keep English for Writing questions, learner essays, English examples, and
canonical IELTS English terminology when pedagogically useful. Do not expose
raw backend identifiers such as `decision_type`, `target_skill`, or
`practice_conflict`.

No full i18n framework is part of Phase 5. Persisted provider/LLM content is
authoritative: the frontend MUST NOT silently machine-translate or alter it,
and Phase 5 MUST NOT modify LLM prompts merely to force Chinese feedback.

## 2. Frozen routes and page responsibilities

| Route | Purpose | Data/action boundary |
| --- | --- | --- |
| `/` or `/dashboard` | learner state, target band, weakest skill, next recommendation | Reads current learner state and presents the current persisted recommendation held by the browser presentation cache; it does not recompute planning. |
| `/setup` | first-time learner creation | Creates one learner with a valid Writing target band and establishes browser learner context. |
| `/writing` | initial Task 2 question, essay editor, word count, evaluation, apply | Submits question + essay to the existing evaluator, renders its response, then applies the returned persisted evaluation identity after P5-04 closes the handoff gap. |
| `/practice/[practiceId]` | authoritative practice workspace | Reads the persisted practice; renders target, objective, instructions, checkpoints, essay editor, submission/evaluation, and complete/replan actions. |

The learner context is browser/session presentation state, not a new backend
source of truth. Direct navigation without a selected learner enters the
appropriate empty/setup state; the UI must not invent a learner ID.

## 3. Frozen primary journey and transitions

```text
/setup create learner
  -> /writing initial question + essay
  -> initial evaluation display
  -> apply learning update
  -> /dashboard state + recommendation
  -> generate practice OR no-practice explanation
  -> /practice/[practiceId] human essay time
  -> submit outcome
  -> persisted evaluation display
  -> complete/replan
  -> /dashboard next recommendation
  -> STOP / HUMAN TIME
```

### Initial writing

1. The learner supplies an English Task 2 question and essay. Display the
   deterministic local word count as an aid; server acceptance remains
   authoritative.
2. `POST /writing/evaluate` returns a complete evaluation display payload and
   `attempt_id`. Until P5-04 provides the persisted `evaluation_id`, the UI
   cannot legally call apply; it shows the evaluation but keeps the apply
   transition unavailable with a development-compatible state, not an inferred
   ID.
3. After P5-04, apply uses the explicit authoritative `evaluation_id` at
   `POST /learners/{learner_id}/writing/evaluations/{evaluation_id}/apply`.
4. Apply returns `recommendation_id` alongside the pure `recommendation`
   decision. The browser then calls `GET /learners/{learner_id}/state` and
   renders the updated learner state plus that recommendation. The decision's
   `state_snapshot` is audit/decision provenance, not a replacement for the
   normal learner-state read endpoint.
5. The frontend MUST NOT recompute learner state or planning.

### Recommendation and practice

1. A `practice` recommendation can be resolved once at
   `POST /learners/{learner_id}/writing/recommendations/{recommendation_id}/practice`.
   Retrying is safe and returns the same durable practice.
2. A `no_practice` outcome does not generate a practice. Present its
   authoritative reason as an understandable Chinese next-step explanation;
   do not offer a fabricated targeted practice.
3. `/practice/[practiceId]` first reads the persisted practice. Its question
   is read-only and authoritative. The submit payload contains **essay only**;
   the browser must never send a replacement question.
4. `submitted` and `reused` submission outcomes provide IDs but not the full
   evaluation. After P5-04, fetch the persisted evaluation through the
   practice-scoped endpoint before rendering it. For `conflict` and
   `in_progress`, do not call complete and do not manufacture an evaluation.
5. Only after a submitted practice and a successful evaluation display can the
   learner select complete. `POST .../complete` applies the existing
   evaluation through Phase 3 and returns `next_recommendation_id` alongside
   the next pure recommendation decision. It does not generate the next
   practice; the ID enables a later legal resolve action.

## 4. UI states

Every remote view/action has distinct `loading`, `empty`, `success`,
`validation error`, `provider failure`, and `persistence failure` states.
The practice/recommendation flow additionally has `no_practice`,
`submission submitted`, `submission reused`, `submission conflict`, and
`submission in_progress` states.

| State | Required presentation behavior |
| --- | --- |
| loading | Disable duplicate action; retain already persisted content where safe; say the action is processing in Chinese. |
| empty | Explain the missing prerequisite and direct the learner to setup, initial writing, or the next valid action. |
| success | Render returned authoritative data and expose only the next lifecycle-valid action. |
| validation error | Map `request_invalid` fields to Chinese field help; preserve the editable user input. |
| provider failure | Explain that evaluation/generation is temporarily unavailable; allow a safe retry; do not claim submission succeeded. |
| persistence failure | Explain that learning data could not be saved; allow a safe retry or refresh; do not expose storage details. |
| no_practice | Display the backend reason in Chinese and stop targeted-practice generation. |
| submission submitted | Record the returned IDs in presentation state, fetch/display evaluation after P5-04, then offer complete. |
| submission reused | State that the same submitted essay was reused; fetch/display the persisted evaluation after P5-04; never resubmit. |
| submission conflict | Explain that this practice already has a different submitted essay; do not overwrite it or call the provider again. |
| submission in_progress | Explain that a submission is still being processed; do not issue another submit or complete action; permit a later refresh/retry. |

## 5. Browser presentation cache (no auth)

Phase 5 may store only presentation/navigation data in localStorage or an
equivalent browser store:

- `currentLearnerId`
- `writingTargetBand`
- `currentRecommendationId`
- `currentRecommendation`

This is a presentation cache, not backend truth. Every business action is
validated by FastAPI and PostgreSQL; the browser must not use cached data to
invent an identity, bypass a lifecycle transition, or recompute a decision.

The browser MUST NOT persist essay content, full evaluation content, provider
payloads, `claim_token`, `submission_fingerprint`, credentials, or secrets.

**V1 limitation:** Phase 5 does not guarantee recovery of an interrupted
learning session after browser storage is cleared or in another device/browser.
Cross-device and cross-session recovery belongs to a future Auth/Product
Hardening phase. Phase 5 does not add authentication, a session backend, a
user profile, or a `GET latest recommendation` endpoint to address this.

## 6. Audited API contract

The supported validation, provider, persistence, ownership, and lifecycle
errors use the safe envelope:

```json
{"error":{"code":"stable_code","message":"safe server message","fields":[]}}
```

The UI maps a recognized `code`, not raw exception text, to Chinese copy. It
may use `fields` only to identify form controls. Any unrecognized or malformed
failure receives one generic Chinese recovery message. The UI MUST NOT display
raw server messages, database/provider details, credentials, claim tokens,
fingerprints, or submitted content from an error response.

| Endpoint | Request the web sends | Success needed by UI | Stable errors relevant to UI |
| --- | --- | --- | --- |
| `POST /learners` | `{ "writing_target_band": {"value":"7.0"} }` | `id`, target band, timestamps (201) | `request_invalid` (422); `persistence_unavailable` (503) |
| `GET /learners/{learner_id}/state` | none | `learner_id`, exactly four states with estimate/evidence/revision | `learner_not_found` (404); `persistence_unavailable` (503) |
| `POST /writing/evaluate` | `{ "question":"…", "essay":"…" }` | `attempt_id`, complete evaluation (criteria, evidence, feedback, bands, word count, metadata, product band) (201) | `request_invalid` (422); provider codes (502/503/504); `persistence_unavailable` (503) |
| `POST /learners/{learner_id}/writing/evaluations/{evaluation_id}/apply` | none | `learning_update_id`, `reused`, persisted `recommendation_id`, and full pure recommendation decision; then the browser reads current state | `learner_not_found`, `evaluation_not_found` (404); `evaluation_conflict` (409); `learning_source_invalid` (422); `persistence_unavailable` (503) |
| `POST /learners/{learner_id}/writing/recommendations/{recommendation_id}/practice` | none | `decision`; either `practice` or `no_practice_reasons` | `practice_not_found` (404); `practice_conflict` (409); provider codes; `persistence_unavailable` (503) |
| `GET /learners/{learner_id}/writing/practices/{practice_id}` | none | immutable practice content, lifecycle state, nullable attempt ID | `practice_not_found` (404) |
| `POST /learners/{learner_id}/writing/practices/{practice_id}/submit` | `{ "essay":"…" }` only | `status` and, for `submitted`/`reused`, `attempt_id` + `evaluation_id` | `request_invalid` (422); `practice_not_found` (404); `practice_conflict` (409); provider codes; `persistence_unavailable` (503) |
| `POST /learners/{learner_id}/writing/practices/{practice_id}/complete` | none | practice/attempt/evaluation/update IDs, persisted `next_recommendation_id`, and full pure next recommendation decision | `practice_not_found` (404); `practice_conflict` (409); `persistence_unavailable` (503) |

Provider codes are `provider_configuration`, `provider_authentication`,
`provider_billing_unavailable`, `provider_timeout`, `provider_rate_limited`,
`provider_unavailable`, `provider_invalid_response`, and
`provider_request_rejected`. Present them with a concise Chinese retry or
support message; never distinguish sensitive account details to the learner.

## 7. Required P5-04 compatibility contract (not implemented)

P5-01 confirmed four additive requirements:

1. The successful initial evaluation handoff needs an explicit persisted
   `evaluation_id`. Preferred compatible change: add `evaluation_id` to the
   existing `201 POST /writing/evaluate` response alongside `attempt_id` and
   `evaluation`. This permits the frozen apply transition without treating
   independent IDs as interchangeable.
2. Add persisted `recommendation_id: int` beside the existing pure
   `recommendation` on `LearningApplyResponse` from
   `POST /learners/{learner_id}/writing/evaluations/{evaluation_id}/apply`.
   Do not put database identity into `PracticeRecommendationDecision`.
3. Add persisted `next_recommendation_id: int` beside the existing pure
   `next_recommendation` on `ClosedLoopResult` from
   `POST /learners/{learner_id}/writing/practices/{practice_id}/complete`.
   Do not put database identity into `PracticeRecommendationDecision`.
4. Add `GET /learners/{learner_id}/writing/practices/{practice_id}/evaluation`.
   It returns the full existing evaluation representation linked from the
   submitted practice's authoritative `attempt_id` to its `WritingEvaluation`.
   It must enforce learner ownership, require lifecycle `submitted`, and use
   safe 4xx/5xx responses. The frontend needs it after `submitted` and
   `reused` outcomes.

These changes must be additive. They must not change scoring, provider prompts,
evaluation policy, learner-state policy, planner policy, practice lifecycle, or
the persistence model.

## 8. Non-goals and future validation

This MVP excludes auth, payments, all non-Writing skills, RAG/vector memory,
agent runtimes, background-job infrastructure, admin/social features, full
i18n, English UI mode, and production deployment architecture.

Future P5-15 browser E2E must use deterministic fakes and isolated PostgreSQL
to prove create -> initial evaluation -> apply -> state/recommendation ->
generate -> submit -> evaluation display -> complete -> next recommendation.
CI must make no live DeepSeek call.
