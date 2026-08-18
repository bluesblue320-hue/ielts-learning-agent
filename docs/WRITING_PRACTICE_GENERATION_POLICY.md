# Writing Practice Generation Policy — Phase 4

**Version:** `writing-practice-generation-v1` (frozen by `P4-03`)
**Status:** ACCEPTED — implementation authority for practice generation

**Central invariant:**

> PracticeRecommendation controls WHAT.
> PracticeGenerator controls HOW.

The LLM MUST NOT choose `target_skill`, learner target, planner reason,
planner version, decision type, or learner state. Generated output is content,
never learner-state authority. No Phase 4 model call may directly mutate
`LearnerSkillState`.

---

## 1. Eligibility

- Generation is **decision-gated**: only a persisted `PracticeRecommendation`
  with `decision_type = practice` may trigger generation.
- `decision_type = no_practice` (reasons `cold_start`, `incomplete_state`,
  `target_achieved`, `target_unset`) MUST produce zero generator calls, zero
  `writing_practices` rows, and a deterministic no-practice outcome.
- `cold_start` has NO Phase 4 bootstrap practice: the learner obtains Writing
  evidence through the existing submission/evaluation path first.
- Eligibility is validated BEFORE any model call by the generation service;
  the database `UNIQUE(recommendation_id)` anchor prevents multiple durable
  practices but does not authorize generation for `no_practice`.

## 2. Input authority

The generator request carries ONLY application-owned authority values read
from the persisted recommendation (read-only):

- `recommendation_id` (identity);
- `target_skill` (the authoritative Phase 3 skill, e.g. `task_response`);
- `learner_target_band` (informational context for content focus);
- `reason_codes`, `planner_version`, decision type (provenance/context);
- generation policy version and prompt version (application-owned).

The request does NOT include learner essays, free-form user text, or any
authority field the model may override.

## 3. Scope of generated content

- **Writing Task 2 ONLY** (IELTS academic Task 2 essays). Task 1, Speaking,
  Reading, Listening are out of scope.
- Supported target skills: exactly the four canonical Phase 3 skills
  (`task_response`, `coherence_and_cohesion`, `lexical_resource`,
  `grammatical_range_and_accuracy`).
- The generated practice is one IELTS Writing Task 2 question focused on the
  target skill, a focus objective, and a small set of targeted
  instructions/checkpoints.

## 4. Structured output contract

Generated output is validated structured data, never free-form text. The
`GeneratedWritingPractice` contract contains:

| Field | Authority | Rules |
| --- | --- | --- |
| `practice_type` | generated | non-blank, stable vocabulary |
| `target_skill` | **mirrors application authority** | MUST equal the persisted recommendation's `target_skill`; mismatch = invalid provider response, no row |
| `question` | generated | non-blank; IELTS Task 2 question; maximum 400 characters |
| `focus_objective` | generated | non-blank; maximum 300 characters |
| `instructions` | generated | 1..6 items; each non-blank, maximum 200 characters |
| `checkpoints` | generated | 1..6 items; each non-blank, maximum 200 characters |
| generator policy version | application | `writing-practice-generation-v1` |
| provenance | application | `provider`, `model`, `prompt_version`, `thinking_mode` |

Authority-mirroring validation: any generated field that mirrors
application-owned authority (e.g. `target_skill`) is validated against the
persisted recommendation; a mismatch is an invalid provider response that
produces NO practice row and a safe normalized failure.

## 5. Prompt ownership & provenance

- Prompt templates are application-owned; each template carries a frozen
  `prompt_version`.
- The provider request is built from the application-owned prompt +
  authority values only; untrusted user content never enters generation.
- Every persisted practice records generator provenance: `provider`, `model`,
  `prompt_version`, `thinking_mode`, and generation policy version.

## 6. Maximum sizes (frozen)

- `question` ≤ 400 characters.
- `focus_objective` ≤ 300 characters.
- `instructions` count 1..6, each ≤ 200 characters.
- `checkpoints` count 1..6, each ≤ 200 characters.

## 7. Safety constraints

- No personal identifying information about the learner in generated content.
- No instruction to fabricate a learner's past performance.
- Content must not encourage plagiarism or reproduction of any real
  examination text verbatim; the question must be an original prompt for the
  target skill.
- Generated content is learner-facing Writing practice only; it never claims
  to be an official IELTS score or guarantee.

## 8. Retry categories & failure behavior

- Generation failures reuse the accepted Phase 2 provider failure
  normalization: `ProviderError` with `ProviderErrorCategory`
  (`configuration`, `authentication`, `billing`, `timeout`, `rate_limit`,
  `transient`, `invalid_response`, `request_rejected`).
- Retryable categories and bounded retry/backoff rules follow the accepted
  Phase 2 `ProviderRetryPolicy` semantics, applied through the focused
  `RetryingPracticeGenerator` (NOT the evaluator-specific `RetryingProvider`
  directly).
- `invalid_response` (including authority-mirroring mismatch) is NOT retried
  as a network failure; it is a deterministic contract failure -> no row,
  safe normalized failure.
- Generation failure -> no `writing_practices` row (SUCCESS-ONLY
  persistence); no failed-generation status or error-category row is
  persisted.

## 9. Idempotency behavior

- One originating `practice` recommendation yields at most one durable
  `writing_practices` row (`UNIQUE(recommendation_id)`).
- Retrying generation returns the existing persisted practice.
- Under a concurrent first-generation race both requests MAY invoke the
  provider; exactly one durable row survives; the losing request resolves the
  persisted winner. Exactly-once provider invocation is NOT guaranteed (v1
  documented limitation).

## 10. Forbidden

- No LLM choice of `target_skill`, learner target, planner reason, planner
  version, decision type, or learner state.
- No generation for `no_practice` or cold-start learners.
- No multi-skill or non-Writing content.
- No mutation of Phase 3/Phase 2 state by the generator.
