# Writing Evaluation API

## Endpoint

`POST /writing/evaluate` accepts an IELTS Writing Task 2 question and essay,
evaluates the submission through the configured provider, validates the structured
result, computes the product band deterministically, and atomically stores the
attempt and evaluation.

A production request requires `IELTS_DEEPSEEK_API_KEY`. Automated tests replace
the provider only through FastAPI dependency overrides; there is no runtime
configuration that selects `FakeProvider`.

### Request

```json
{
  "question": "Some people prefer city life. Discuss both views.",
  "essay": "The essay text..."
}
```

Both values must be non-blank strings and unexpected fields are rejected.
`question` accepts at most 2,000 characters and `essay` at most 20,000
characters; exceeding either limit returns `422 request_invalid` before any
provider or database work. Word count is the deterministic number of
non-whitespace tokens in the essay.

An essay below 250 words remains a valid submission. Its word count and the
versioned rubric's task-length guidance are supplied as evaluation evidence;
the provider does not decide request validity. This product behavior is not a
claim of official score equivalence.

### Successful response

A successful request returns `201 Created`:

```json
{
  "attempt_id": 1,
  "evaluation_id": 1,
  "evaluation": {
    "criteria": {
      "task_response": {
        "band": {"value": "6.5"},
        "evidence": ["Relevant evidence from the essay."],
        "feedback": "Develop the supporting example."
      },
      "coherence_and_cohesion": {
        "band": {"value": "6.5"},
        "evidence": ["Paragraphing is clear."],
        "feedback": "Strengthen transitions."
      },
      "lexical_resource": {
        "band": {"value": "6.5"},
        "evidence": ["Vocabulary is generally appropriate."],
        "feedback": "Use more precise collocations."
      },
      "grammatical_range_and_accuracy": {
        "band": {"value": "6.5"},
        "evidence": ["Complex sentences are attempted."],
        "feedback": "Improve clause control."
      }
    },
    "strengths": ["The position is clear."],
    "weaknesses": ["Some support remains general."],
    "error_tags": ["article-use"],
    "recommended_skills": ["supporting examples"],
    "feedback": "Prioritize specific evidence.",
    "metadata": {
      "provider": "deepseek",
      "model": "deepseek-v4-pro",
      "prompt_version": "writing-v2",
      "rubric_version": "writing-task2-v1",
      "scoring_policy_version": "writing-product-band-v1",
      "thinking_mode": "disabled"
    },
    "word_count": 276,
    "product_band": {"value": "6.5"}
  }
}
```

Provider output cannot supply or override `word_count`, trusted metadata, or
`product_band`.

The application owns provider/model, prompt, rubric, scoring-policy, and
thinking-mode metadata. Provider output contains only the qualitative evaluation
fields. The `writing-task2-v1` request contract includes explicit definitions
and summarized integer band anchors from 0 through 9 for all four criteria,
half-band guidance, task-length guidance, the deterministic submission word
count, scoring policy, and output schema. It is versioned for reproducibility;
it is not represented as an official IELTS publication.

## Product-band policy

The four inputs are Task Response, Coherence and Cohesion, Lexical Resource, and
Grammatical Range and Accuracy. Each must be an IELTS half-band value from 0 to
9 and each has weight 0.25.

The application computes their weighted mean and quantizes it to the nearest
0.5 using `ROUND_HALF_UP`; an exact tie is rounded upward. The output boundaries
are 0 and 9. Missing criteria, values outside the boundaries, and values outside
0.5 increments are rejected before aggregation.

This is an explicit product policy. It is not a claim that the value exactly
reproduces an official final IELTS Writing band.

## Retry and failure behavior

Provider calls have at most three total attempts. Only normalized `timeout`,
`rate_limit`, and `transient` failures are retried, with deterministic bounded
exponential delays of 0.25 seconds then 0.5 seconds. Configuration,
authentication, account/billing, invalid structured output, and rejected
requests are not retried. Validation and database failures are never
provider-retried.

Errors use this safe response shape and do not include submitted content,
credentials, raw provider bodies, request IDs, or database exception text:

```json
{
  "error": {
    "code": "provider_timeout",
    "message": "Writing evaluation provider timed out.",
    "fields": []
  }
}
```

| Status | Error code | Meaning |
| --- | --- | --- |
| `422` | `request_invalid` | Request schema validation failed |
| `502` | `provider_invalid_response` | Provider result failed structured validation |
| `502` | `provider_request_rejected` | Provider rejected the request |
| `503` | `provider_configuration` | Provider configuration is missing or invalid |
| `503` | `provider_authentication` | Provider authentication failed |
| `503` | `provider_billing_unavailable` | Provider account or billing cannot process the request |
| `503` | `provider_rate_limited` | Rate limit persisted after bounded retries |
| `503` | `provider_unavailable` | Transient failure persisted after bounded retries |
| `503` | `persistence_unavailable` | Atomic persistence failed and was rolled back |
| `504` | `provider_timeout` | Timeout persisted after bounded retries |

Question and essay content remain untrusted data in provider request
construction. Deterministic FakeProvider tests verify the application-level
trust boundary, structured-output validation, and safe responses. They do not
prove that a real LLM cannot be prompt-injected, and perfect prompt-injection
prevention is not claimed.

## Health endpoints

- `GET /health/live` reports process liveness without external access.
- `GET /health/ready` checks PostgreSQL and returns `503` when it is unavailable.

## Adaptive Writing practice endpoints

Phase 4 keeps the lifecycle actions separate under
`/learners/{learner_id}/writing`:

- `POST /recommendations/{recommendation_id}/practice` resolves an existing
  Phase 3 decision. A `practice` decision returns one durable practice;
  `no_practice` returns persisted reason codes with no provider call or row.
- `GET /practices/{practice_id}` returns the durable practice and lifecycle state.
- `GET /learners/{learner_id}/writing/practices/{practice_id}/evaluation`
  requires a learner-owned practice in the `submitted` lifecycle state, follows
  the authoritative `practice.attempt_id`, and returns `attempt_id`,
  `evaluation_id`, and the persisted evaluation. It does not call the
  LLM/provider again.
- `POST /practices/{practice_id}/submit` accepts `{ "essay": "..." }` only;
  the server supplies the persisted generated question to the existing evaluator.
- `POST /practices/{practice_id}/complete` applies the persisted evaluation
  through Phase 3 and returns the next recommendation without generating it.

The lifecycle is `generated -> submission_in_progress -> submitted`. Provider
calls are outside database transactions; PostgreSQL constraints and row locks
enforce durable ownership and one logical submission.


## Grounded Writing guidance

`GET /learners/{learner_id}/writing/guidance` returns the provider-free
`writing-grounded-guidance-v1` projection for the latest accepted
`LearningUpdate.id DESC`. It includes the safe learner-state summary, nullable
current recommendation, grounded guidance items, application-owned citations,
and exact knowledge/retrieval versions. It exposes no raw Planner context,
Memory provenance, claim metadata, provider reasoning, or filesystem paths.

No generic Knowledge search or runtime URL fetch endpoint is available.
## Phase 5 web compatibility

`POST /writing/evaluate` returns `attempt_id`, persisted `evaluation_id`, and `evaluation`. `POST /learners/{learner_id}/writing/evaluations/{evaluation_id}/apply` returns `learning_update_id`, `reused`, persisted `recommendation_id`, and `recommendation`. Complete returns `next_recommendation_id` beside `next_recommendation`.