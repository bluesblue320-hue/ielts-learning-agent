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

Both values must be non-blank strings and unexpected fields are rejected. Word
count is the number of non-whitespace tokens in the essay. An essay below 250
words remains a valid submission; the API does not treat 250 words as a request
validation threshold.

### Successful response

A successful request returns `201 Created`:

```json
{
  "attempt_id": 1,
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
      "prompt_version": "writing-v1"
    },
    "word_count": 276,
    "product_band": {"value": "6.5"}
  }
}
```

Provider output cannot supply or override `word_count`, trusted metadata, or
`product_band`.

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
`rate_limit`, and `transient` failures are retried. Configuration,
authentication, invalid structured output, and rejected requests are not
retried. Validation and database failures are never provider-retried.

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
