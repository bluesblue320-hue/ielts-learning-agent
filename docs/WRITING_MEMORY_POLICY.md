# Writing Learning Memory Policy

## Status

- **Node:** `P6-02` — Hierarchical Learning Memory Contract Freeze
- **State:** `COMPLETE` (frozen and accepted by the P6-01/P6-02 design run)
- **Memory version:** `writing-memory-v1`
- **Progress-policy version:** `writing-progress-v1`
- **Authority:** [PHASE6_GRAPH.md](PHASE6_GRAPH.md), executed under
  [DEVELOPMENT_LOOP.md](DEVELOPMENT_LOOP.md)

This document is the normative specification for the Phase 6 Writing Learning
Memory subsystem. It is intentionally free of schema, model, service, route,
and frontend implementation, which belong to later nodes (`P6-03` and after).
Sections are separated into **normative policy**, **examples**,
**implementation notes**, and **deferred decisions**.

This policy is adapted from the architectural ideas of hierarchical agent
memory (progressive disclosure, provenance, memory/runtime separation) for an
IELTS adaptive learning system. It does not copy any external memory
architecture mechanically, and it does not introduce an external memory vendor.

---

## 1. Normative policy

### 1.1 Memory hierarchy

Learning memory is structured as four levels:

```text
L3 — Learner Learning Profile
  -> L2 — Learning Pattern
      -> L1 — Learning Atom
          -> L0 — Learning Episode
              -> authoritative persisted PostgreSQL rows
```

| Level | Name | Semantics | Question it answers |
| --- | --- | --- | --- |
| L0 | Learning Episode | One authoritative learner-owned historical learning event | What happened? |
| L1 | Learning Atom | One small structured fact derived from an episode | What was learned? |
| L2 | Learning Pattern | One deterministic longitudinal pattern over multiple L1/L0 facts | What pattern is emerging? |
| L3 | Learner Profile | The learner's longitudinal Writing condition summary | What does the system know long-term? |

Every derived object (L1/L2/L3) must remain traceable to its sources. No
memory fact without a source may exist.

### 1.2 L0 — Learning Episode

**Definition.** An L0 Learning Episode is the authoritative record that one
persisted Writing evaluation was accepted into one learner's learning state.

**Anchor.** The preferred and only episode anchor is the persisted
`LearningUpdate` row, because it proves that a persisted evaluation has been
applied to a specific learner (learner-owned) and records the frozen policy
versions and acceptance time.

**Source chain.** Each episode reconstructs its authoritative source:

```text
LearningUpdate
  -> WritingEvaluation (via writing_evaluation_id)
      -> WritingAttempt (via evaluation.attempt_id)
  -> LearningEvidence (four rows, via learning_update_id)
  -> PracticeRecommendation (via learning_update_id, at most one)
  -> optional WritingPractice (via practice.attempt_id == evaluation.attempt_id)
```

**Ownership.** A raw `WritingAttempt` or `WritingEvaluation` alone is NOT
learner-owned memory; only an accepted `LearningUpdate` makes it learner-owned.
The global uniqueness of `learning_updates.writing_evaluation_id` guarantees
one evaluation is owned by at most one learner.

**Episode type.** Each episode is deterministically classified:

- `targeted_practice` ⇔ exactly one `WritingPractice` references the episode's
  evaluation attempt (`writing_practices.attempt_id` UNIQUE);
- `initial_writing` ⇔ no `WritingPractice` references that attempt.

A submitted-but-not-completed practice has an attempt and evaluation but no
`LearningUpdate` yet; it is not an episode until completed. It remains visible
in practice history as a pending practice and in context as a resume point.

**L0 storage.** L0 is NOT duplicated. It IS the existing normalized PostgreSQL
rows (`learning_updates`, `learning_evidence`, `writing_evaluations`,
`writing_attempts`, `practice_recommendations`, `writing_practices`).

### 1.3 L1 — Learning Atom

**Definition.** An L1 Learning Atom is one small structured learning fact
derived from one L0 episode, with provenance back to its authoritative source.

**Atom kinds.** Exactly four kinds are recognized in `writing-memory-v1`:

| Atom kind | Content | Authoritative source |
| --- | --- | --- |
| `skill_observation` | `skill`, `observed_band`, canonical order values, provenance | one `LearningEvidence` row |
| `practice_completed` | `skill`, practice id, episode id, completion time | `WritingPractice` (submitted) + its applied `LearningUpdate` |
| `target_snapshot` | `writing_target_band` at episode time | `PracticeRecommendation.learner_target_band` / `Learner.writing_target_band` |
| `recommendation_observation` | the full planner decision | one `PracticeRecommendation` row |

**Provenance requirement.** Every L1 atom must expose stable source ids:

```text
L1 atom
  -> source episode (LearningUpdate.id)
  -> persisted evidence / evaluation / practice rows (LearningEvidence.id,
     WritingPractice.id, PracticeRecommendation.id, WritingEvaluation.id)
```

Provenance-free atoms are forbidden. If a source cannot be identified, the
atom must not be produced.

**L1 storage.** In `writing-memory-v1`, L1 atoms are read-model projections of
existing rows; `skill_observation` and `recommendation_observation` already
exist as persisted rows. No new L1 table is created.

**Tradeoff (documented).** Materializing L1 would duplicate immutable rows
and re-encode existing uniqueness/provenance constraints without adding
capability at v1 scale (four skills, half-band observations, small counts).
Recomputation is a projection (no aggregation cost). Materialization is
deferred unless a proven requirement appears (see section 1.15).

### 1.4 L2 — Learning Pattern

**Definition.** An L2 Learning Pattern is a deterministic longitudinal fact
derived from multiple L1/L0 facts for one canonical skill.

**Pattern kinds** (`writing-progress-v1`):

| Pattern | Type | Values |
| --- | --- | --- |
| `trend` | status | `improving` \| `stable` \| `declining` \| `insufficient_history` |
| `persistent_gap` | boolean | `true` \| `false` (+ `insufficient_history` status) |
| `recent_observation_count` | count | number of canonical observations in the trend window |
| `recent_practice_count` | count | completed targeted practices for the skill in the recent episode window |
| `latest_observation_time` | timestamp | `source_created_at` of the last canonical observation |

**Determinism.** L2 MUST remain structured and deterministic. An LLM MUST NOT
invent, judge, or narrate authoritative longitudinal facts. Numeric trend and
gap decisions are pure functions of persisted observations.

**Drill-down.** Every L2 pattern must expose its source observations and
episodes:

```text
L2 pattern
  -> source L1 atoms / source observations (LearningEvidence.id list)
  -> source L0 episodes (LearningUpdate.id list)
```

**L2 storage.** Read-model / computed. No L2 table in `writing-memory-v1`.

### 1.5 L3 — Learner Learning Profile

**Definition.** L3 is the Learner Learning Profile: a structured summary of the
learner's longitudinal Writing condition. It is NOT a personality persona and
NOT a generic chatbot profile.

**Content** (`writing-memory-v1`):

```text
learner_id
writing_target_band                       (current, from Learner)
current four-skill state                  (read from LearnerSkillState: estimate,
                                           evidence_count, revision, last_evidence_id,
                                           state_policy_version) — reference, not replacement
per-skill:
  current_estimate
  evidence_count
  trend
  persistent_gap
  recent_observation_count
  recent_practice_count
  latest_observation_time
  last_episode_id
memory_version                            (writing-memory-v1)
progress_version                          (writing-progress-v1)
```

**Traceability.** The profile must remain traceable to L2/L1/L0. Every
per-skill summary exposes source ids (last episode id, trend source
observation ids, persistent-gap source observation ids).

**Unsupported statements.** Unsupported qualitative statements such as "the
learner is bad at grammar" MUST NOT be stored as memory facts unless they
correspond to a defined structured deterministic contract. The preferred shape
is:

```json
{
  "skill": "grammatical_range_and_accuracy",
  "trend": "improving",
  "persistent_gap": true,
  "current_estimate": 6.00,
  "target_band": 7.0
}
```

**L3 storage.** Read-model / computed in `writing-memory-v1`. No L3 table.

### 1.6 Progressive disclosure

Frozen rule:

```text
L3 profile
  -> L2 patterns if detail required
  -> L1 atoms if evidence required
  -> L0 episodes if source verification required
```

Normal product and future Agent use MUST prefer higher-level memory first. The
system MUST NOT send every historical essay/evaluation into an LLM or Agent
context by default. High-level memory must be drillable back to authoritative
evidence through stable source ids.

### 1.7 Provenance contract

This is a major Phase 6 invariant. Derived memory must remain auditable:

```text
L3 Learner Profile
  -> L2 Pattern IDs / derivation references
      -> L1 Atom IDs / observation references
          -> L0 Learning Episode
              -> authoritative persisted rows
```

If materialized rows are ever proposed, they must preserve source references.
In `writing-memory-v1` (read-model derivation), every response schema MUST
still expose enough stable provenance for drill-down: `learning_update_id`,
`learning_evidence_id`, `writing_evaluation_id`, `writing_practice_id`,
`recommendation_id`, `attempt_id` where applicable. Never produce an
authoritative memory fact with no source.

### 1.8 History ordering

Learner-owned L0 episodes are returned in deterministic order:

```text
LearningUpdate.created_at DESC
LearningUpdate.id DESC
```

`created_at` is the primary key; `id` is the deterministic tie-breaker (the
BigInteger sequence guarantees total order). No other ordering is valid.

### 1.9 Trend policy

**Version:** `writing-progress-v1`. **Window:** `TREND_WINDOW = 3`.

**Series.** The canonical trend series for one skill is the criterion observed
band sequence over the canonical per-skill observation ordering
(`LearningEvidence.source_created_at ASC`, `source_attempt_id ASC`). This is
the frozen P6-01 decision; EWMA estimates are NOT mixed into the trend series
(see 3.2 tradeoff in PHASE6_GRAPH.md).

**Computation.** For one skill:

```text
usable = canonical observations for the skill
if count(usable) < 3:
    trend = insufficient_history
else:
    latest  = usable[-1].observed_band      # exact Decimal
    oldest  = usable[-3].observed_band      # exact Decimal
    delta   = latest - oldest               # exact Decimal arithmetic
    if delta >= +0.25: trend = improving
    elif delta <= -0.25: trend = declining
    else: trend = stable
```

**Constraints.** Exact `Decimal` arithmetic. No LLM. No hidden weighting. No
wall-clock decay. No confidence score.

### 1.10 Persistent-gap policy

**Version:** `writing-progress-v1`. **Window:** `TREND_WINDOW = 3`.

For one skill, using the same canonical observation sequence as the trend
policy:

```text
if count(usable) < 3:
    persistent_gap = false
    status = insufficient_history
else:
    target = learner's current writing_target_band (Learner row, exact Decimal)
    if usable[-3].observed_band < target
       and usable[-2].observed_band < target
       and usable[-1].observed_band < target:
        persistent_gap = true
    else:
        persistent_gap = false
```

**Constraints.** No confidence score. No LLM. No hidden heuristic weighting.
The current `Learner.writing_target_band` is the live reference (the learner
target has no update endpoint in the implemented system; if a target-change
feature is added later, the policy must be revisited in a future version).

### 1.11 Practice-history semantics

**Counting basis.** Only durable, successfully generated `WritingPractice`
rows count as practices. No practice row → no practice.

**Lifecycle semantics** (frozen):

| Lifecycle state | Memory meaning |
| --- | --- |
| `generated` | durable practice exists; not completed |
| `submission_in_progress` | claimed; not finalized; not completed |
| `submitted` | durable submitted practice; **completed in memory semantics only if its evaluation has been applied** (a `LearningUpdate` exists for the linked evaluation) |

Generated-but-unsubmitted practice MUST NOT be called "completed". Only
`submitted` + applied counts as `practice_completed`.

**Derived metrics** (per skill):

- `practice_count` = durable generated practices for the skill (all lifecycle
  states).
- `completed_practice_count` = `submitted` + applied practices for the skill.
- `latest_practice` = most recent durable practice by `created_at DESC`,
  `id DESC`.
- `latest_completed_practice_time` = `LearningUpdate.created_at` of the most
  recent applied practice episode (or the practice `updated_at` when the link
  is unambiguous); the frozen representation is the episode `occurred_at`.
- `recent_practice_count` = completed practices for the skill among the latest
  `TREND_WINDOW` episodes (episode ordering per 1.8).

**Linkage** (frozen, 1:1 at every hop):

```text
practice -> attempt -> evaluation -> learning update
WritingPractice.attempt_id
  -> WritingAttempt.id
  -> WritingEvaluation.attempt_id (UNIQUE)
  -> LearningUpdate.writing_evaluation_id (UNIQUE)
```

### 1.12 State vs memory boundary

This distinction is mandatory.

- **Learner State** answers "what is the learner estimated to be now?" It is
  the existing materialized `LearnerSkillState` (plus `Learner`), updated by
  the frozen `writing-state-ewma-v1` engine. It is authoritative current state.
- **Memory** answers "what happened before, and what longitudinal patterns can
  be derived from that history?" It is L0–L3 as defined above.

`LearningMemory` MUST NOT replace `LearnerSkillState`. Memory MUST NOT become
the authoritative current state. The L3 profile may READ current state fields
for presentation, but it must reference them, not duplicate the state
computation, and never override them.

### 1.13 Planner boundary

`writing-practice-gap-v1` is NOT modified in Phase 6. The current planner
remains deterministic and uses its existing frozen inputs. Phase 6 MUST NOT
add memory-aware reason codes, trend inputs, persistent-gap inputs,
free-form weaknesses, `error_tags`, or qualitative memory to the current
planner. A future separately versioned planner may consume memory after
Phase 6 proves the memory semantics.

### 1.14 Qualitative-data boundary

Phase 2 qualitative provider fields — `strengths`, `weaknesses`, `error_tags`,
`recommended_skills`, and `feedback` — remain historical qualitative evidence
at L0. They are displayed as episode content (provenance) only.

`error_tags` and `recommended_skills` are free-form provider strings, not a
frozen application taxonomy. Therefore they MUST NOT become authoritative L2/L3
mastery facts or planner inputs in Phase 6.

### 1.15 Read-model vs materialization decision

**Frozen decision (`writing-memory-v1`):** L1/L2/L3 are derived read models.
No new table is created; no migration is required.

Materialization is justified only by a proven requirement:

- latency targets at large history that recomputation cannot meet;
- Agent/LLM context needing stable opaque memory ids that persisted row ids do
  not already provide;
- cross-cutting queries made slow by repeated recomputation.

If any future materialization is proposed, it must first explain (per P6-01):
the invariant that requires persistence, why existing records are insufficient,
why recomputation is insufficient, the ownership model, the provenance model,
and the migration implications — and it must go through a future graph node
with migration permission.

### 1.16 Memory adapter boundary (future design, not implemented)

The application does not depend on any external memory vendor. A future
conceptual boundary is:

```text
LearningMemoryProvider
  - get_history(...)
  - get_episode(...)
  - get_progress(...)
  - get_profile(...)
  - get_context(...)
  - recall(...)
```

Possible future adapters: `PostgresLearningMemoryProvider` (the Phase 6 read
models) and a hypothetical `TencentDBLearningMemoryAdapter`.

**Decision for Phase 6:** the adapter abstraction is NOT introduced as a
runtime dependency. Phase 6 implements read-model services directly over the
existing persistence layer. The boundary above is a documented design sketch
only; a provider protocol will be introduced only when a second concrete
provider is actually required. No abstraction for appearance.

### 1.17 Public product read contracts (candidates — frozen shape)

The smallest coherent API is four read endpoints (no separate profile
endpoint):

| Endpoint | Answers | Content |
| --- | --- | --- |
| `GET /learners/{learner_id}/writing/history` | What did I do? | Learner-owned L0 episode list in frozen order (1.8), episode type, occurred_at, skill summary, recommendation summary, provenance ids |
| `GET /learners/{learner_id}/writing/history/{episode_id}` | What happened in this episode? | Full L0 reconstruction: update, evaluation (criteria, feedback, strengths/weaknesses/error_tags/recommended_skills, metadata, product band), attempt (question, essay, word count), evidence set, recommendation, linked practice |
| `GET /learners/{learner_id}/writing/progress` | How have I changed? | L3 profile section (target, current four-skill state, per-skill summary) + L2 per-skill patterns with provenance |
| `GET /learners/{learner_id}/writing/context` | Where should the learner continue? | Server-authoritative resume context: current state, latest recommendation, latest relevant practice + lifecycle, deterministic resume action |

**Context/resume semantics.** Resume recovers server-authoritative learning
context for a known learner ID. It does NOT mean authentication, cross-device
login, account discovery, or identity recovery. Browser storage remains an
identity hint; PostgreSQL remains the learning truth.

**Resume action** (deterministic; no automatic next-practice generation):

```text
no episodes                        -> initial_writing
latest recommendation = practice and
  no practice for that recommendation -> generate_practice
latest practice = generated        -> submit_practice
latest practice = submission_in_progress -> await_submission (recheck)
latest practice = submitted and evaluation not applied -> complete_practice
latest practice = submitted and applied -> latest recommendation action
                                            (practice -> generate_practice;
                                             no_practice -> stop / no_action)
```

The endpoint returns the action and its supporting context; it never generates
a practice.

### 1.18 Version identifiers

```text
writing-memory-v1      (memory hierarchy, semantics, provenance, boundaries)
writing-progress-v1    (trend policy, persistent-gap policy, practice-history windows)
```

The Phase 3/4 versions remain authoritative and unchanged:
`writing-core-v1`, `writing-state-ewma-v1`, `writing-practice-gap-v1`,
`writing-practice-generation-v1`, `writing-practice-product-v1`.

---

## 2. Required policy examples

### 2.1 Trend examples (`writing-progress-v1`)

Reference implementation: `tests/test_progress_policy.py` (future, P6-06).

| Example | Canonical observed bands | Trend |
| --- | --- | --- |
| A. insufficient | `6.0` | `insufficient_history` |
| B. insufficient | `6.0, 6.5` | `insufficient_history` |
| C. improving | `6.0, 6.5, 7.0` | `improving` (delta +1.0) |
| D. improving boundary | `6.0, 6.5, 6.5` | `improving` (delta +0.5 ≥ 0.25) |
| E. stable | `6.5, 6.0, 6.5` | `stable` (delta 0.0) |
| F. stable boundary | `6.5, 6.5, 6.5` | `stable` |
| G. declining | `7.0, 6.5, 6.0` | `declining` (delta −1.0) |
| H. declining boundary | `7.0, 6.5, 6.5` | `declining` (delta −0.5 ≤ −0.25) |
| I. four observations | `6.0, 6.5, 7.0, 6.5` | window over `usable[-3:]` = `6.5, 7.0, 6.5` → delta 0.0 → `stable` |

### 2.2 Persistent-gap examples

Reference implementation: `tests/test_progress_policy.py` (future, P6-06).
Target = `7.0`.

| Example | Canonical observed bands | persistent_gap |
| --- | --- | --- |
| A. insufficient | `6.0, 6.5` | `false` (`insufficient_history`) |
| B. gap | `6.0, 6.5, 6.5` | `true` (all < 7.0) |
| C. no gap | `6.0, 7.0, 6.5` | `false` (7.0 not < 7.0) |
| D. no gap achieved | `7.0, 7.5, 8.0` | `false` |
| E. mixed | `5.5, 6.0, 7.0` | `false` (latest window includes 7.0) |

### 2.3 Practice-history examples

| Scenario | Memory result |
| --- | --- |
| practice generated, never submitted | `practice_count` includes it; `completed_practice_count` excludes it; latest practice shows `generated` |
| practice claimed (`submission_in_progress`) | not completed; never called completed |
| practice submitted, evaluation applied | `completed_practice_count` includes it; `practice_completed` atom exists |
| practice submitted, evaluation NOT applied | durable `submitted` practice; not completed; context resume action = `complete_practice` |

---

## 3. Implementation notes

- The frozen P6-02 constants (e.g., `TREND_WINDOW = 3`, `+0.25` / `−0.25`
  thresholds) will be materialized by a future node (P6-06) in a constants
  module mirroring this document; they contain no engine logic.
- The trend/persistent-gap engine (P6-06) consumes the canonical per-skill
  observation sequence exactly as defined; it never infers rules from data and
  never calls an LLM.
- Read models (P6-04/P6-05/P6-07) only SELECT and project existing rows; they
  perform no mutation.
- The reference examples above will be encoded by the future
  `tests/test_progress_policy.py` exactly.

## 4. Deferred decisions

- Whether a future separately versioned planner may consume L2/L3 memory
  inputs (explicitly out of scope for Phase 6).
- Materialization of L1/L2/L3 (only if a proven requirement appears; see
  1.15).
- The memory-adapter runtime protocol (only when a second concrete provider is
  required; see 1.16).
- Any wall-clock recency or decay semantics (v1 uses canonical-sequence
  windows only).
- Any change to the learner target after creation (no update endpoint exists;
  the policy uses the current `Learner.writing_target_band`).
