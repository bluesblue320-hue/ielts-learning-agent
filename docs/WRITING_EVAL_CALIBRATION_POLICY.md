# Writing Evaluation & Calibration Policy — Phase 10

**Policy version:** `writing-eval-calibration-v1`
**Status:** FROZEN DESIGN CONTRACT — P10-02
**Scope:** Writing Task 2 evaluation calibration and deterministic application-contract evaluation.
**Implementation authority:** This policy defines P10-03 onward only after the
Formal Phase 10 External Design Review is explicitly approved.

## 1. Purpose, scope, and non-goals

Phase 10 makes evaluation evidence reviewable without changing the frozen
production meaning of `writing-task2-v1`. It separates deterministic
application-contract regression from observational Writing-score calibration.

This policy does not change Writing scoring, rubric ownership, Learner State,
Memory, Planner, Practice semantics, Knowledge semantics, Agent authority, or
any Phase 1–9 versioned contract. It does not create a public Eval API,
dashboard, production trace table, persistence migration, or runtime feature.

The policy is implementation-neutral: future nodes may use pytest, a narrow
internal CLI, JSON, Markdown/text reports, and CI artifacts/output. No generic
Eval framework, vector database, RAG framework, LangChain, LangGraph, Redis,
Celery, Kafka, or new provider dependency is authorized.

## 2. Stable identifiers

These identifiers are frozen for Phase 10 v1. They are stable contract names,
not new runtime versions or permission to introduce their implementation now.

| Concept | Frozen identifier |
| --- | --- |
| Policy | `writing-eval-calibration-v1` |
| Regression corpus | `writing-eval-regression-corpus-v1` |
| Calibration corpus | `writing-score-calibration-corpus-v1` |
| Regression-case schema | `writing-eval-regression-case-v1` |
| Calibration-case schema | `writing-score-calibration-case-v1` |
| Reference-label schema | `writing-score-reference-label-v1` |
| Provider-capture schema | `writing-score-provider-capture-v1` |
| Eval-result schema | `writing-eval-result-v1` |
| Calibration-result schema | `writing-score-calibration-result-v1` |
| Failure taxonomy | `writing-eval-failure-taxonomy-v1` |
| Report | `writing-eval-report-v1` |

## 3. Three execution modes

### 3.1 Deterministic Regression Mode

Purpose: prove frozen application contracts and lifecycle semantics. It is
provider-free and network-free at execution time, repeatable, isolated, and the
only mode eligible to become a required merge-gating CI path.

Inputs may use canonical application inputs plus a frozen fake-provider payload
or a captured provider payload. Expected outputs are frozen structured
application outcomes, not human IELTS scoring opinions. Applicable contracts
include schema validation, product-band aggregation, error handling,
persistence, LearningUpdate, State, Memory, Planner, recommendation ownership,
Knowledge grounding, practice lifecycle, Agent trajectory, chronology,
idempotency, authority, and fail-closed behavior.

`provider variance != code regression`. A different live model score alone
must never fail Deterministic Regression Mode.

### 3.2 Live Calibration Mode

Purpose: measure current Writing score behavior against admissible reference
evidence. It invokes a real provider and is observational and nondeterministic;
it is never a deterministic merge gate.

It compares system criterion scores and product score with admissible reference
criterion scores and overall score where available. Provider/model,
thinking-mode, prompt, rubric, scoring-policy, and run/config metadata must be
recorded. A live disagreement is calibration evidence, not automatically a code
regression.

### 3.3 Calibration Replay Mode

Purpose: recompute calibration analysis from captured provider outputs. It makes
no provider call and no network request, and is reproducible for the same
captured input. It analyzes historical capture; it does not claim that a new
live provider call would reproduce the same score.

## 4. Corpus separation and generated-practice scope

There are exactly two distinct corpora. They must never be silently merged.

| Corpus | Purpose | Expected truth |
| --- | --- | --- |
| `writing-eval-regression-corpus-v1` | deterministic application-contract regression | frozen application outcomes |
| `writing-score-calibration-corpus-v1` | Writing scoring calibration | reference evidence with uncertainty |

The regression corpus covers structured provider validation and retry,
application-owned product-band aggregation, persistence, LearningUpdate, State
replay, Memory and Planner ties, recommendation ownership, practice freshness,
Knowledge IDs/citations, Agent bounds/trajectory, and deterministic historical
regressions. It has no runtime network dependency and its expected outputs are
not human IELTS scoring opinions.

The calibration corpus contains question/essay input, reference scoring
evidence, raw rater labels, provenance, evidence tier, ambiguity state,
adjudication, and provider-capture metadata. It must not become production
expected-output truth: `reference label != production scoring contract`, and
`calibration disagreement != deterministic regression`.

Generated-practice semantic or pedagogical quality is
**OUT_OF_SCOPE for Phase 10 Writing score calibration v1**. No practice-quality
human labels, practice-quality calibration corpus, or practice-quality LLM judge
gate is authorized. Deterministic checks may cover recommendation ownership,
target skill/band, generation version, schema, Knowledge IDs/grounding,
freshness/staleness, provider failure, replay, and idempotency.

## 5. Existing-contract preservation

The evaluator retains application-owned request, rubric, prompt, metadata, and
product-band aggregation. Provider structured output controls only the existing
qualitative fields and remains Pydantic-validated. Four criterion half-bands are
aggregated by the existing `writing-task2-v1` algorithm; a provider cannot
override the product band or application metadata.

Existing ownership, atomicity, retry, idempotency, chronology, and lifecycle
contracts remain authoritative. In particular, deterministic cases must respect
the existing learner lock and `LearningUpdate.writing_evaluation_id` idempotency
anchor; State chronology (`WritingAttempt.created_at ASC, id ASC`), Memory
chronology (`LearningUpdate.created_at DESC, id DESC`), and current Agent/
guidance observation (`LearningUpdate.id DESC`) remain purpose-specific.

Knowledge remains source-backed and cannot redefine scoring or select a Planner
target. A generated practice mirrors persisted recommendation authority and
does not obtain learner-state authority. Agent evidence is limited to its
existing bounded structured response; this policy creates no new agent power.

## 6. Deterministic result and severity model

The exact result status values are:

```text
pass
fail
not_applicable
blocked
invalid_case
```

The exact severity values are:

```text
veto
major
minor
info
```

`pass` means all applicable frozen assertions passed. `fail` means an
applicable assertion failed. `not_applicable` means a valid case does not apply
to a selected evaluator. `blocked` means trusted execution could not proceed
without asserting success. `invalid_case` means the case itself is malformed,
unsupported, incomplete, or otherwise not safely evaluable. No blended or
averaged score may hide a severe correctness failure.

### 6.1 VETO semantics

The following are at least `veto` failures when applicable evidence proves them:

- fabricated success after an authoritative failure;
- score-authority bypass;
- Learner State authority bypass;
- wrong learner or wrong episode ownership;
- wrong recommendation ownership;
- unknown Knowledge provenance presented as grounded;
- deterministic replay violation in Deterministic Regression Mode;
- an Eval runner touching non-isolated or production-like mutable data; or
- a malformed case silently treated as `pass`.

These categories enforce existing authority semantics; they do not invent new
production behavior. An evaluator must not downgrade, average away, or mask a
veto with unrelated successful checks.

## 7. First-failure attribution

Every future Eval result must identify the first failing boundary, rather than
only returning `fail`. Later failures cannot hide an earlier causal failure.

The frozen conceptual failure dimensions are:

```text
case_validation
provider_contract
evaluation
persistence
learning_update
state
memory
planner
recommendation
knowledge
practice_generation
practice_submission
practice_completion
agent_trajectory
authority
calibration
reporting
infrastructure
```

P10-11 may implement codes and taxonomy mechanics, but must preserve these
boundaries and this first-failure ordering principle.

## 8. Regression-case contract

P10-03 must represent every deterministic regression case with concepts
equivalent to:

```text
case_id
schema_version
corpus_version
description
category
mode
input
provider_fixture or captured_fixture_reference where applicable
expected_structured_outcomes
expected_lifecycle_evidence
expected_trajectory_constraints
applicable_evaluators
severity_expectations
provenance or historical_regression_reference where applicable
```

The implementation must fail closed for an unknown field where strict schema
applies, unknown enum, duplicate case ID, unknown fixture reference,
unsupported schema version, invalid expected outcome, or missing required
evidence. Corpus records cannot contain executable arbitrary Python code.

## 9. Calibration reference model

Calibration evidence has these frozen tiers:

| Tier | Admissibility and authority |
| --- | --- |
| A | Authoritative or officially published scoring evidence, where licensing and source constraints allow use. |
| B | Independent human-reviewed or adjudicated evidence. |
| C | Exploratory model-assisted evidence; never examiner truth or correctness authority. |

Single-rater human opinion must remain distinguishable from multi-rater or
adjudicated evidence. When independent human ratings exist, retain raw rater ID
or pseudonymous identifier, four criterion ratings, overall rating when
available, rating timestamp/version when relevant, and provenance. Preserve
adjudicated labels separately. Never overwrite raw independent ratings or
average away disagreement before preserving it.

Each calibration case conceptually requires:

```text
case_id
schema_version
corpus_version
question
essay
reference_labels
reference_tier
provenance
ambiguity
adjudication_metadata
provider_capture_references
```

Reference scores support the four IELTS Writing criteria individually. Missing
criterion data remains missing; it must not be silently inferred from an overall
score.

### 9.1 Ambiguity and inter-rater policy

The exact ambiguity values are:

```text
unambiguous
rater_disagreement
insufficient_reference
adjudication_pending
excluded_from_primary_metric
```

No essay is forced into a supposedly authoritative label. Reports must keep
substantial human disagreement visible when interpreting system-reference
disagreement. Where enough human ratings exist, calculate and report human
exact agreement, human within-0.5 agreement, mean absolute human-rater
difference, and criterion-level disagreement separately from system metrics.

## 10. Calibration metrics and interpretation

For each applicable population, reports must provide exact-band agreement,
within-0.5 agreement, within-1.0 agreement, criterion-level absolute error,
mean absolute error, signed error/bias, score distribution, sample count, and
results by evidence tier. They must also disclose sample count, reference tier,
ambiguity, provider/model version, prompt version, rubric version, and material
limitations. Calibration must not be reduced to one aggregate number.

`contract correctness != reference-score agreement`.

| Condition | Required interpretation |
| --- | --- |
| Contract `pass` and calibration disagreement | Retain `pass`; record calibration mismatch. |
| Contract `fail` and calibration agreement | Retain `fail`. |

A reference-like provider score never excuses invalid schema, authority bypass,
wrong learner ownership, bad lifecycle, fabricated success, or unknown
Knowledge provenance.

## 11. Evidence, trace, and isolation

Trajectory evaluation may use only application-owned structured responses,
persisted rows, stable IDs, explicit status/outcome enums, `AgentTurnResponse`,
`AgentStep`, `initial_observation`, `final_observation`, `stop_reason`,
Knowledge IDs, recommendation/practice ownership, and provider-capture
metadata.

It must not require private chain-of-thought, hidden model reasoning, or an
unstructured internal scratchpad. There is **no production trace table for
Phase 10 v1** and no public Eval API. If a later node establishes a genuine
evidence gap, only minimal, test-only, non-semantic, internal instrumentation
may be considered.

Deterministic Regression Mode runs on an isolated test database. It must not
mutate production data, personal user records, or uncontrolled external systems.
Each case is repeatable, self-contained, and deterministically resettable. Reuse
existing PostgreSQL pytest isolation where possible. The default is **no Eval
persistence migration**; no new table is authorized unless a future approved
design amendment proves necessity.

## 12. Provider captures and replay

Each Live Calibration capture conceptually records:

```text
capture_id
case_id
provider
model
thinking_mode
prompt_version
rubric_version
scoring_policy_version
provider_structured_payload
application_normalized_result
capture_timestamp
run_or_config_version
```

Never store an API key, secret, private chain-of-thought, or provider hidden
reasoning. A captured provider output is immutable input to Calibration Replay
Mode.

## 13. Anti-overfitting and historical promotion

Future implementation must not special-case production behavior by Eval case
ID, add production branches solely to pass a known case, weaken expected outputs
because the implementation differs, or change rubric, Planner, Memory, or
Knowledge authority to improve a pass rate. A failure is attributed as an
implementation defect, test defect, case defect, reference uncertainty, or
contract conflict; it is never automatically normalized.

P10-14 may promote a historical failure only when the failure is understood,
the frozen intended contract is known, deterministic representation is possible,
stable evidence exists, and the case does not encode an accidental
implementation detail. A promoted case preserves its origin, historical failure
semantics, fix/protection evidence, and expected contract.

## 14. Controlled updates to cases, labels, and captures

The frozen schemas, enum values, corpus separation, and semantic rules may not
be silently changed. A future change to them requires a documented policy
amendment and the review authority required by the graph. A regression case may
change only to correct a demonstrated case defect or to record an explicitly
approved production-contract change; it must retain the prior rationale and
state why the expected outcome changed. It must never be weakened merely to
match a current implementation.

Reference labels, raw ratings, adjudications, and provider captures are
append-only evidence. They may be superseded for analysis only with a recorded
reason, provenance, editor or process identity, and timestamp/version; the raw
original remains available for review. A capture or label that lacks admissible
provenance is excluded or marked ambiguous rather than promoted to correctness
authority. No update may merge the two corpora or turn reference evidence into
production expected-output truth.

## 15. CI, optional LLM judges, and reporting

Only Deterministic Regression Mode may become required merge-gating CI. Live
Calibration Mode must never gate a deterministic merge. Calibration Replay may
run as reproducible CI analysis, but cannot masquerade as live calibration.
P10-02 does not modify CI. The P10-01 finding remains: the runtime is suitable,
the current Phase 10 branch push trigger is not configured, and a pull-request
trigger is available; P10-15 owns any CI integration.

No LLM judge is required for Phase 10 deterministic correctness. If a later
approved node adds an optional secondary judge, it must be versioned; record
provider/model and prompt; expose nondeterminism; never make it the sole veto
authority; never let it override deterministic checks; and never fabricate a
`pass` when unavailable or failed. It must not evaluate private chain-of-thought.

Machine-readable results must expose concepts equivalent to run ID, mode, case
ID/version, evaluators executed, status, severity, first failing boundary,
failure codes, structured evidence references, provider metadata where
applicable, and suitable timing/execution metadata. Human reports summarize
pass/fail counts, veto failures, first-failure distribution, regression
categories, calibration metrics, sample sizes, reference tiers, human
disagreement, provider/model versions, and limitations. A web dashboard is not
required or authorized.

## 16. Design gate and implementation boundary

P10-02 completes the design contract only. P10-03 and all later implementation
nodes remain blocked until the Formal Phase 10 External Design Review explicitly
approves this policy together with `docs/PHASE10_GRAPH.md` and the P10-01 audit.
No policy text authorizes an Eval harness, schemas, corpora, labels, captures,
runner, report generator, CI gate, migration, public API, or dashboard now.
