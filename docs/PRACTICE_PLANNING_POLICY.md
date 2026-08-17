# Writing Practice Planning Policy

## Status

- **Node:** `P3-08` — Practice Planning Policy
- **Planner version:** `writing-practice-gap-v1`
- **Constants module:** `app/learner/planning_policy.py`
- **Decision schemas:** `app/schemas/planning.py`
- **Authority:** [PHASE3_GRAPH.md](PHASE3_GRAPH.md), executed under
  [DEVELOPMENT_LOOP.md](DEVELOPMENT_LOOP.md)

This document is the normative specification for the deterministic Writing
practice planner. It is free of planner algorithm, persistence, and LLM
behavior; the production planner implementation belongs to P3-09. Sections are
separated into **normative policy**, **examples**, **implementation notes**, and
**deferred decisions**.

---

## 1. Normative policy

### 1.1 Scope and responsibility

The planner is deterministic and versioned `writing-practice-gap-v1`. Its only
responsibility is:

- determine **what** Writing skill should be practiced next; or
- deterministically record that no evidence-based practice target is required.

It must not generate lessons, exercises, explanations, prompts, tasks, question
banks, or any study content.

### 1.2 Input contract

The policy consumes only:

- the learner Writing target band;
- the four canonical learner skill states;
- `evidence_count` for each skill;
- the decision-time state snapshot;
- accepted P3-02 state-policy outputs.

Canonical skills are exactly:

- `task_response`
- `coherence_and_cohesion`
- `lexical_resource`
- `grammatical_range_and_accuracy`

The planner must not consume `strengths`, `weaknesses`, `error_tags`,
`recommended_skills`, `feedback`, raw essay text, LLM output, or provider
reasoning.

### 1.3 Target gap

For every observed skill:

```text
gap = learner_target_band - estimated_band
```

Example (target `7.0`): `task_response` 6.00 → gap 1.00;
`coherence_and_cohesion` 6.50 → 0.50; `lexical_resource` 6.75 → 0.25;
`grammatical_range_and_accuracy` 6.50 → 0.50. The skill with the largest
positive gap is the preferred practice target.

The already-materialized estimate is used directly; it is not rounded or
transformed before computing the gap. Arithmetic uses exact `Decimal`.

### 1.4 Normal practice decision

When the learner target exists, all four skills are observed, and at least one
skill has `gap > 0`:

```text
decision_type = "practice"
target_skill = skill with largest positive gap
current_estimate = selected skill estimated_band
learner_target_band = learner target
primary reason = largest_target_gap
```

### 1.5 Explicit tie-break priority

Freeze this planning tie-break priority:

```text
1. task_response
2. coherence_and_cohesion
3. lexical_resource
4. grammatical_range_and_accuracy
```

It is used only when two or more candidate skills share exactly the same maximum
positive target gap. It is not a claim of academic importance. Tuple/dict/ORM/
database/iteration order must never select a skill. When tie-breaking applies,
reason codes include, in this stable order: `largest_target_gap`,
`priority_tiebreak`.

### 1.6 Evidence threshold

Freeze:

```text
MIN_ESTABLISHED_EVIDENCE_COUNT = 3
```

- 0 evidence: `unobserved`
- 1 or 2 evidence: `insufficient evidence`
- 3 or more: `established` for v1 planning

Insufficient evidence does **not** block a normal practice recommendation. For a
practice decision, add `insufficient_evidence` when the **selected** target
skill has `evidence_count < 3`. No synthetic confidence score is used.

### 1.7 Target achieved

If all four skills are observed and `estimated_band >= learner_target_band` for
all four, then:

```text
decision_type = "no_practice"
target_skill = null
current_estimate = null
primary reason = target_achieved
```

If any skill has `evidence_count < 3`, append `insufficient_evidence`.

### 1.8 Cold start

If all four skill states are UNOBSERVED:

```text
decision_type = "no_practice"
target_skill = null
current_estimate = null
reason_codes = [cold_start]
```

No default skill (such as `task_response`) is arbitrarily chosen.

### 1.9 Incomplete state

If some skills are observed but at least one remains UNOBSERVED:

```text
decision_type = "no_practice"
target_skill = null
current_estimate = null
reason_codes = [incomplete_state]
```

No partial recommendation is computed from an incomplete four-skill state. This
branch is defensive: the normal Phase 3 flow produces four observations
atomically.

### 1.10 Target unset

If the planner input has no target:

```text
decision_type = "no_practice"
target_skill = null
learner_target_band = null
current_estimate = null
reason_codes = [target_unset]
```

The existing `Learner` schema is not modified to make `writing_target_band`
nullable; this is a planner-boundary/defensive contract.

### 1.11 Reason-code taxonomy

Freeze exactly these reason codes for planner v1:

```text
largest_target_gap
priority_tiebreak
insufficient_evidence
target_achieved
cold_start
incomplete_state
target_unset
```

Primary reasons:

```text
largest_target_gap
target_achieved
cold_start
incomplete_state
target_unset
```

Qualifiers:

```text
priority_tiebreak
insufficient_evidence
```

A primary reason must always come first. Example valid ordering:

```text
["largest_target_gap", "priority_tiebreak", "insufficient_evidence"]
```

### 1.12 Decision contract

Frozen structured decision fields:

```text
decision_type
target_skill
learner_target_band
current_estimate
reason_codes
planner_version
state_snapshot
```

`decision_type` is `practice` or `no_practice`. Schemas are strict Pydantic v2
with extra fields forbidden.

### 1.13 Practice validation

For `practice`:

- `target_skill` non-null;
- `learner_target_band` non-null;
- `current_estimate` non-null;
- `reason_codes` includes `largest_target_gap`;
- `planner_version` equals `writing-practice-gap-v1`.

### 1.14 No-practice validation

For `no_practice`:

- `target_skill` null;
- `current_estimate` null;
- for `target_unset`, `learner_target_band` null;
- for all other no-practice reasons, `learner_target_band` present.

`no_practice` + non-null `target_skill` and `practice` + null `target_skill` are
both rejected.

### 1.15 Exactly one primary reason

Every decision has exactly one primary reason. Allowed primaries are the five
listed in 1.11. Multiple-primary combinations are rejected.

Qualifier validity:

- `priority_tiebreak` is valid only with `largest_target_gap`;
- `insufficient_evidence` is valid only with `largest_target_gap` or
  `target_achieved`.

Semantically contradictory combinations are rejected.

### 1.16 State snapshot

Every decision preserves the complete decision-time state snapshot. It reuses
the accepted P3-03 four-skill state-set structure (`LearnerSkillStateSet`) and
preserves, for all four canonical skills: `learner_id`, `skill`,
`estimated_band`, `evidence_count`, `state_policy_version`, `revision`,
`last_evidence_id`, and the `updated_at` timestamps already present in the
accepted state schema. No unstructured arbitrary dict is used. The snapshot is
for auditability and must support reconstructing why a decision was made.

### 1.17 Determinism

The same learner target, state snapshot, evidence counts, and planner version
always produce the same logical decision, independent of input dictionary order,
database row order, ORM iteration order, request order, and transaction commit
order. No LLM or random behavior is permitted.

### 1.18 Snapshot / reason consistency

The decision contract guarantees that reason semantics agree with the persisted
state snapshot. Inconsistent input is rejected, never normalized.

- **target_achieved** requires `learner_target_band` non-null, all four canonical
  skills observed, and every `estimated_band >= learner_target_band.value`.
  `insufficient_evidence` is bidirectional with the snapshot: present exactly
  when at least one skill has `evidence_count < MIN_ESTABLISHED_EVIDENCE_COUNT`.
- **cold_start** requires all four skills UNOBSERVED (`estimated_band` null,
  `evidence_count` 0, `last_evidence_id` null, `revision` 0).
- **incomplete_state** requires a mixed snapshot: at least one observed and at
  least one unobserved skill.
- **target_unset** places no requirement on the snapshot shape; the absence of a
  learner target takes precedence, and any valid four-skill snapshot may be
  retained for auditability.
- For **practice**, `insufficient_evidence` is bidirectional with the selected
  skill: present exactly when
  `state_snapshot[target_skill].evidence_count < MIN_ESTABLISHED_EVIDENCE_COUNT`.

The schema validates only these local invariants. It does not recompute all
skill gaps or re-run tie-break selection to prove that `target_skill` is the
largest-gap skill; that selection algorithm belongs to P3-09.

---

## 2. Required policy examples

The reference decision function in `tests/test_practice_planning_policy.py`
encodes these normative examples exactly.

| Example | Input (target) | States | Decision | target_skill | reason_codes |
| --- | --- | --- | --- | --- | --- |
| A | 7.0 | TR 6.0, CC 6.5, LR 6.75, GRA 6.5 | practice | task_response | largest_target_gap |
| B | 7.0 | TR 6.0, CC 6.0, LR 6.5, GRA 6.5 | practice | task_response | largest_target_gap, priority_tiebreak |
| C | 7.0 | TR 5.5/c1, CC 6.0/c1, LR 6.5/c1, GRA 6.0/c1 | practice | task_response | largest_target_gap, insufficient_evidence |
| D | 7.0 | TR 7.0, CC 7.25, LR 7.0, GRA 7.0 (count≥3) | no_practice | null | target_achieved |
| E | 7.0 | same values, counts = 1 | no_practice | null | target_achieved, insufficient_evidence |
| F | any | all UNOBSERVED | no_practice | null | cold_start |
| G | 7.0 | TR/CC/GRA observed, LR UNOBSERVED | no_practice | null | incomplete_state |
| H | null | (any) | no_practice | null | target_unset |
| I | 7.0 | any valid set, reordered input | identical decision | — | — |
| J | 6.5 | all four = 6.50 | no_practice | null | target_achieved |
| K | 6.5 | TR 6.49, others ≥ 6.50 | practice | task_response | largest_target_gap |

---

## 3. Implementation notes

- Frozen constants live in `app/learner/planning_policy.py`; the decision
  contract lives in `app/schemas/planning.py`.
- The production `plan_practice(...)` / `select_skill(...)` algorithm is owned by
  P3-09. P3-08 introduces no decision function in application code.
- A test-local reference decision function is used only to validate the frozen
  examples.

## 4. Deferred decisions

- The production planner implementation (P3-09).
- Persistence of `PracticeRecommendation` (P3-04/P3-05) and the
  application/transaction orchestration that writes one decision per update
  (P3-10).
- Concurrency and idempotency hardening around decision persistence (P3-12).
