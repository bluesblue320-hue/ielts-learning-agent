# Writing Learner-State Policy

## Status

- **Node:** `P3-02` — Writing Skill Taxonomy & State Update Policy
- **State:** `COMPLETE` (frozen and accepted)
- **Taxonomy version:** `writing-core-v1`
- **State-policy version:** `writing-state-ewma-v1`
- **Frozen constants module:** `app/learner/writing_policy.py`
- **Authority:** [PHASE3_GRAPH.md](PHASE3_GRAPH.md), executed under
  [DEVELOPMENT_LOOP.md](DEVELOPMENT_LOOP.md)

This document is the normative specification for the Writing learner-state
policy. It is intentionally free of updater, planner, schema, model, or
persistence implementation, which belong to later nodes. Sections below are
explicitly separated into **normative policy**, **examples**, **implementation
notes**, and **deferred decisions**.

---

## 1. Normative policy

### 1.1 Skill taxonomy

The canonical Writing skill taxonomy is versioned `writing-core-v1` and contains
exactly four skills:

- `task_response`
- `coherence_and_cohesion`
- `lexical_resource`
- `grammatical_range_and_accuracy`

No finer-grained vocabulary, grammar, error-tag, or skill ontology is introduced.
The tuple order is presentation-only and is **not** a ranking or practice
priority.

Phase 2 free-text fields — `strengths`, `weaknesses`, `error_tags`,
`recommended_skills`, and `feedback` — are **not** canonical learner-state
inputs. Learner state is driven only by the four structured criterion bands.

### 1.2 State policy

The state policy is versioned `writing-state-ewma-v1`. Each of the four skills
maintains an independent evidence sequence and an independent derived
learner-state estimate.

Observed criterion evidence retains the Phase 2 IELTS half-band semantics:

- valid values: `0, 0.5, 1.0, ..., 9.0`
- the learner Writing target also retains existing IELTS half-band semantics.

The derived `LearnerSkillState` estimate is **not** a half-band score and is not
forced to the half-band `BandScore` contract.

### 1.3 State-update formula

For one skill with canonically ordered observations `X1, X2, ..., Xn`:

```text
S1 = X1
Sn = 0.5 * Xn + 0.5 * S(n-1)          for n >= 2
```

- The weighting coefficient alpha is frozen at `0.5`.
- Alpha is **not** configurable in Phase 3 v1.
- Arithmetic uses exact `Decimal` values.
- No Bayesian estimation, BKT, IRT, learned weights, or other mastery model is
  permitted.

### 1.4 Materialized precision

- **Observed evidence:** IELTS half-band only.
- **Derived state:** range `0.00` through `9.00`.
- **Final persisted/materialized precision:** 2 decimal places.
- **Final quantization:** `Decimal("0.01")`.
- **Rounding:** `ROUND_HALF_UP`.

Intermediate EWMA steps are **never** rounded. The correct behavior is:

```text
canonical full replay
  -> retain exact Decimal intermediate values
  -> final state result
  -> quantize once to 0.01
```

### 1.5 Canonical evidence order

Canonical cross-evaluation ordering is:

```text
WritingAttempt.created_at ASC
WritingAttempt.id ASC
```

The source ordering values are immutable provenance/order data and must be
preserved with `LearningEvidence` by later nodes so replay never depends on
request-processing history.

Canonical order must **not** depend on:

- HTTP request arrival order
- `LearningUpdate` creation order
- `LearningEvidence` insertion order
- database transaction commit order
- `LearningEvidence` primary key
- ORM default order

Tie behavior:

- `WritingAttempt.created_at` is the primary key.
- `WritingAttempt.id` is the deterministic tie-breaker.

### 1.6 Late-arriving evidence

If canonical source order is `A` then `B`, the application sequences `A -> B`
and `B -> A` must eventually produce the same final materialized state, equal to
`canonical replay(A, B)`.

P3-02 freezes this correctness requirement but does not select the optimization
strategy. P3-07 may use full canonical replay, order-independent equivalent
math, or another mathematically equivalent deterministic implementation. For
Phase 3 v1, full replay is the preferred simple strategy.

### 1.7 Initialization

- **No accepted evidence:** the state is `UNOBSERVED`.
- No default learner level is invented. Learner skills are **not** initialized
  to `5.0`, `6.0`, or any other synthetic prior.
- **First accepted observation:** `S1 = X1`. Example: first
  `lexical_resource` evidence of `6.5` yields `estimated state = 6.50` and
  `evidence_count = 1`.

### 1.8 Recency

Recency in v1 is sequence-based EWMA recency only. There is no wall-clock decay.
A learner who stops practicing for 30 days does not automatically lose band
state. State changes only when accepted evidence changes.

### 1.9 Outliers

Phase 3 v1 performs **no** outlier filtering. Any valid persisted Phase 2
criterion score is valid evidence, regardless of distance from previous state.
Invalid Phase 2 score values remain invalid at the evidence boundary.

### 1.10 Duplicates / idempotency

The same persisted `WritingEvaluation` affects learner state at most once. At the
application layer, the same learner plus the same `WritingEvaluation` returns or
reuses the existing logical `LearningUpdate` and produces no duplicate effect. It
must not add another evidence set, increment `evidence_count`, update state
again, or create another planning decision.

If duplicate canonical evidence exists in persisted history despite the database
invariants, replay treats it as an invariant violation. Corrupted history is
**not** silently deduplicated.

### 1.11 Missing evidence

One accepted `WritingEvaluation` yields exactly four criterion evidence items:

```text
task_response
coherence_and_cohesion
lexical_resource
grammatical_range_and_accuracy
```

`3/4` is invalid. If any canonical criterion is missing or invalid, the whole
learning update is rejected; learner state is never partially updated.

### 1.12 Evidence count

`evidence_count` is the number of unique accepted `LearningEvidence`
observations for one learner and one skill that participate in the accepted
canonical replay.

- Duplicate API application does not increment `evidence_count`.
- A failed transaction does not increment `evidence_count`.

With four successfully applied Writing evaluations, normal state is:

```text
task_response evidence_count = 4
coherence_and_cohesion evidence_count = 4
lexical_resource evidence_count = 4
grammatical_range_and_accuracy evidence_count = 4
```

### 1.13 Last evidence

`last_evidence_id` identifies the evidence that is **last in canonical source
order**, not the evidence most recently inserted into PostgreSQL.

### 1.14 Revision semantics

`revision` is the monotonic version of successful materialized
learner-skill-state writes.

- First successful materialization: `revision = 1`.
- A later accepted evidence set that changes/rebuilds materialized state:
  `revision += 1`.
- A late-arriving older evidence that causes canonical replay and successful
  materialization: `revision += 1`.
- Idempotent application of an already accepted evaluation must **not**
  increment `revision`.

P3-12 may later select the PostgreSQL-safe concurrency mechanism that uses this
revision contract.

### 1.15 Confidence

No confidence field is introduced in Phase 3 v1. There is no `confidence = 0.8`
or equivalent synthetic field. P3-08 may use `evidence_count` directly for
planning categories such as cold start or insufficient evidence; exact planner
thresholds belong to P3-08, not P3-02.

### 1.16 Rebuild invariant

For the same learner, skill, accepted evidence set, canonical ordering, taxonomy
version, and state-policy version:

```text
replay(all canonical evidence) == materialized LearnerSkillState
```

This holds regardless of request arrival order, transaction commit order, or
insertion order.

---

## 2. Required policy examples

The reference calculator in `tests/test_writing_state_policy.py` encodes these
normative examples exactly.

| Example | Evidence | Final materialized state |
| --- | --- | --- |
| A. first evidence | `6.5` | `6.50` |
| B. repeated equal evidence | `6.5, 6.5, 6.5` | `6.50` |
| C. improving sequence | `6.0, 6.5, 7.0` | `6.63` |
| D. declining sequence | `7.0, 6.5, 6.0` | `6.38` |
| E. mixed sequence | `6.0, 6.5, 7.0, 6.5` | `6.56` |
| F. lower bound | `0.0` | `0.00` |
| G. upper bound | `9.0` | `9.00` |
| H. canonical-order independence | `A = 6.0`, `B = 7.0` | `6.50` |
| I. same-timestamp tie | `attempt_id` 100 then 101 | order `100, 101` |
| J. no evidence | (none) | `UNOBSERVED` |

Detailed working for the non-trivial examples:

```text
C. S1 = 6.0
   S2 = 6.25
   S3 = 6.625          -> 6.63 (quantized once)

D. S1 = 7.0
   S2 = 6.75
   S3 = 6.375          -> 6.38

E. S1 = 6.0
   S2 = 6.25
   S3 = 6.625
   S4 = 6.5625         -> 6.56

H. canonical replay(A, B):
   S1 = 6.0
   S2 = 6.5            -> 6.50
   applying B -> A also yields 6.50 after canonical replay
```

---

## 3. Implementation notes

- The frozen constants live in `app/learner/writing_policy.py` and are the only
  runtime artifacts P3-02 introduces. They contain no functions that compute or
  mutate state.
- The state-update engine (P3-07) consumes these constants and must reproduce
  this policy exactly; it never infers rules from data or calls an LLM.
- The reference calculator used by the P3-02 tests is test-local only and is not
  the production implementation.

## 4. Deferred decisions

- The concrete `UNOBSERVED` representation (absent row vs. sentinel value) is a
  schema/engine concern owned by P3-03 and P3-07.
- Whether replay uses full canonical replay or order-independent equivalent math
  is owned by P3-07.
- The PostgreSQL-safe concurrency mechanism using the revision contract is owned
  by P3-12.
- Planner thresholds over `evidence_count` (cold start, insufficient evidence)
  are owned by P3-08.
- Any confidence measure, if ever adopted, is out of scope for Phase 3 v1.
