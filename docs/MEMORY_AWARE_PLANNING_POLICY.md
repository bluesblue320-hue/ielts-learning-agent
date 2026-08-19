# Memory-Aware Planning Policy

## Status and version

This is the frozen Phase 7 design contract for the deterministic Writing
planner version:

```text
planner_version: writing-practice-gap-memory-v2
context_schema_version: writing-practice-gap-memory-v2-context-v1
memory_version: writing-memory-v1
progress_version: writing-progress-v1
```

It governs the future P7-03+ implementation only. It does not change
`writing-practice-gap-v1`, reinterpret a historical v1 recommendation, or
authorize implementation in this design run.

## 1. Responsibility and boundaries

The v2 planner deterministically chooses one canonical Writing criterion to
practice next, or records a no-practice decision. Its purpose is deliberately
narrow:

```text
authoritative current learner state chooses the maximum gap
longitudinal memory resolves only an exact maximum-gap tie
```

The planner decides **what** to practice. The practice generator continues to
decide **how** to construct an exercise from a persisted target skill. Memory
context must never be sent to the generator or its provider prompt.

The following are forbidden planner inputs: raw essays, questions, feedback,
strengths, weaknesses, error tags, recommended skills, provider/model metadata,
LLM reasoning, embeddings, semantic retrieval, or wall-clock decay. v2 is not
an agent runtime, LLM planner, reinforcement-learning system, RAG feature, or
multi-agent orchestration.

## 2. Authoritative inputs

The v2 decision accepts:

1. the existing `LearnerSkillStateSet` decision-time snapshot;
2. the learner's Writing target band; and
3. one strict application-owned `MemoryAwarePlanningContext`.

The context has exactly these planner-relevant fields for every canonical
Writing skill, in canonical skill order:

```text
trend: declining | stable | improving | insufficient_history
persistent_gap: boolean
persistent_gap_status: established | insufficient_history
recent_practice_count: non-negative integer
source_observation_ids: ordered list[LearningEvidence.id]
source_episode_ids: ordered list[LearningUpdate.id]
recent_practice_source_episode_ids: ordered list[LearningUpdate.id]
```

It additionally carries `memory_version`, `progress_version`, and
`context_schema_version`. It is not a `WritingProgressResponse`; the public
response has unrelated presentation/read-model fields and must not become a
write-path dependency. The future context builder owns a focused domain schema
and uses Phase 6's frozen pattern and episode-window primitives.

`source_observation_ids` and `source_episode_ids` identify the same canonical
trend/persistent-gap evidence window. `recent_practice_source_episode_ids`
identifies the frozen latest-three L0 episode window used to count completed
targeted practices. These ids are audit provenance, not user-facing text.

## 3. Current-state precedence and no-practice branches

Before consulting Memory, v2 must preserve v1 behavior exactly and in order:

1. absent target → `no_practice(target_unset)`;
2. all four skills unobserved → `no_practice(cold_start)`;
3. one to three observed skills → `no_practice(incomplete_state)`;
4. all four observed and at/above target → `no_practice(target_achieved)`,
   including v1's `insufficient_evidence` qualifier where applicable.

Memory must not turn `target_achieved` into a practice. For normal practice,
v2 calculates the four target gaps exactly as v1:

```text
gap(skill) = learner_target_band - current estimated_band(skill)
maximum = maximum(gap(skill))
candidates = all skills whose gap equals maximum exactly
```

The preceding branches ensure `maximum` is positive. If `candidates` contains
one skill, that skill is selected and no Memory tie-break is applied. Memory
cannot override a uniquely largest positive current target gap.

## 4. Exact-tie hierarchy

Only if two or more skills have an exactly equal maximum positive gap, apply
these stages in order. A stage may replace the current candidate set only when
its output is nonempty and strictly smaller. A non-narrowing stage records its
consideration but leaves the candidate set unchanged.

### 4.1 Persistent gap

Take candidates for which both conditions hold:

```text
persistent_gap is true
persistent_gap_status is established
```

If this set narrows the candidates, retain it. An `insufficient_history` status
is not evidence of a persistent gap and cannot qualify a skill at this stage.

### 4.2 Trend

Trend is usable only when **every** remaining candidate has an established
trend (`declining`, `stable`, or `improving`), not `insufficient_history`.
When usable, retain candidates with the highest deterministic concern priority:

```text
declining > stable > improving
```

If any remaining candidate has `insufficient_history`, trend does not narrow
the set. Insufficient history is neither favorable nor unfavorable; it is not
silently ranked as an established trend. This conservative rule avoids choosing
a skill merely because another equally weak skill has more observed history.

### 4.3 Recent practice

Retain candidates with the lowest `recent_practice_count`. This uses the
existing `writing-progress-v1` completed-targeted-practice count in the latest
three learner-owned L0 episodes. Generated, claimed, and submitted-but-
unapplied practices do not count.

### 4.4 Canonical fallback

If candidates still tie, select the first in the frozen v1 order:

```text
task_response
coherence_and_cohesion
lexical_resource
grammatical_range_and_accuracy
```

No scoring weights, aggregate score, confidence score, or unbounded heuristic
is permitted.

## 5. Reason codes and selection trace

Reason codes retain their v1 meaning and allowed ordering:

- Every normal v2 practice begins with `largest_target_gap`.
- Add `priority_tiebreak` only when the final canonical fallback narrows an
  unresolved exact tie.
- Add `insufficient_evidence` exactly when the selected state snapshot has
  fewer than three evidence rows, as in v1.
- No new Memory reason code is introduced.

V2 auditability comes from a strict `selection_trace` inside the context
snapshot, not a widened reason-code taxonomy. Its minimum shape is:

```text
initial_max_gap_candidates: ordered canonical skill list
stages: ordered list of {
  stage: persistent_gap | trend | recent_practice | canonical_priority
  candidates_before: ordered canonical skill list
  candidates_after: ordered canonical skill list
  narrowed: boolean
}
selected_skill: canonical skill
```

For a unique maximum gap, `stages` is empty. For an exact tie, each stage
reached while at least two candidates remain is recorded, including a
non-narrowing Memory stage. Stages after a single candidate is selected are
omitted. Lists use canonical v1 skill order; no query/insertion ordering is
allowed to affect the trace.

The trace does not duplicate Memory data: the corresponding per-skill values
and provenance reside once in the same context snapshot.

## 6. Decision-time snapshot and persistence

`PracticeRecommendation.state_snapshot` remains the complete decision-time
state record for both versions. It is insufficient for v2 because it cannot
preserve longitudinal signals that later accepted evidence or practices can
change.

P7-04 must add the following nullable JSONB field to the existing
`practice_recommendations` table:

```text
planner_context_snapshot JSONB NULL
```

The migration is narrow and additive. It must accept only `NULL` or a JSON
object at the database layer. A strict Pydantic/domain contract enforces:

```text
writing-practice-gap-v1          -> planner_context_snapshot is NULL
writing-practice-gap-memory-v2   -> planner_context_snapshot is present,
                                    schema-valid, and contains selection_trace
```

No new table and no generic planner-history table is permitted. Historical v1
rows remain unchanged; they are never backfilled or reclassified. The v2
snapshot is the authoritative answer to “why was this recommendation selected
then?” Recomputing present-day Memory may be useful for current planning but
must never replace a historical snapshot.

## 7. Schema versioning and public compatibility

The current `PracticeRecommendationDecision` is historically v1-specific. A
future implementation must preserve a strict v1 model (with a compatibility
alias where existing imports require it) and add a strict v2 model. The public
decision type is their discriminated union on `planner_version`:

```text
PracticeRecommendationDecisionV1
  planner_version = writing-practice-gap-v1
  planner_context_snapshot absent / persisted NULL

PracticeRecommendationDecisionV2
  planner_version = writing-practice-gap-memory-v2
  planner_context_snapshot = strict v2 context and trace
```

The apply response, practice-completion response, episode-detail reconstruction,
history/context reads, and typed web client must use that union in P7-08/P7-09.
Practice generation remains version-agnostic: it validates and uses the
persisted decision's target skill and existing generator request fields; it
does not receive context snapshot content.

For a v2 decision, a public explanation may report only structured factors
that actually narrowed an exact tie: equal current gaps, established persistent
gap, established declining/stable/improving trend, lower recent practice count,
or canonical fallback. It must derive from the persisted trace, preserve the
existing v1 explanation, and never expose raw ids or ask an LLM to explain.

## 8. Transaction and late-arrival semantics

The v2 context is derived inside the existing atomic learning-application
transaction after the new `LearningEvidence` rows are flushed and all four
states are canonically rebuilt, but before its recommendation is persisted and
committed. There is no provider/LLM call in this transaction.

Trend and persistent gap use Phase 6 canonical per-skill evidence order:

```text
source_created_at ASC, source_attempt_id ASC
```

Thus newly inserted evidence participates immediately even if it describes an
older attempt. Recent practice remains deliberately different: it uses the
latest three learner-owned L0 episodes by
`LearningUpdate.created_at DESC, LearningUpdate.id DESC`. An applied targeted
practice present in that episode window participates immediately. These are
frozen Phase 6 semantics, not apply-order heuristics.

Late arrival can legitimately alter a new decision's derived Memory context.
It cannot change a persisted old v2 decision, because its decision-time
context, source ids, trace, state snapshot, target, version, and reason codes
are retained on that recommendation.

## 9. Normative examples

All gaps below are exact Decimal values and all candidate lists use canonical
priority order.

| Example | Input/result |
| --- | --- |
| A. Unique gap | Target 7.0; TR 5.5 and all others 6.0 → select TR. Grammar's persistent/declining Memory is not consulted for selection. |
| B. Persistent gap | TR and CC both gap 1.0; only CC is `persistent_gap=true, established` → select CC; trace says persistent-gap narrowed. |
| C. Trend | Equal-gap candidates both have no qualifying persistent gap; TR is declining and CC stable → select TR; trace says trend narrowed. |
| D. Recency | Equal gaps, equal persistent state, equal established trend; TR recent count 2 and CC 0 → select CC; trace says recent-practice narrowed. |
| E. Fallback | Equal gaps and all Memory stages do not narrow → select the first remaining canonical skill; trace says canonical-priority narrowed and reason includes `priority_tiebreak`. |
| F. Insufficient Memory | Equal gaps; one candidate has `insufficient_history` trend → trend does not narrow. Continue to recency, then fallback if needed. |
| G. Low evidence | A selected v2 target has evidence count 2 → selection remains valid and reason adds `insufficient_evidence`, exactly as v1. |
| H. Target achieved | Every current state is at/above target → `no_practice(target_achieved)` even if a historical trend is declining. |
| I. Cold start | No state is observed → `no_practice(cold_start)`; no Memory context affects selection. |
| J. Late arrival | An older source attempt is applied after newer evidence; its evidence enters canonical trend order immediately. The new decision snapshots the changed context; old v2 snapshots stay unchanged. |
| K. Historical v1 | A row with `writing-practice-gap-v1` and NULL context reconstructs with the original v1 model and original reason semantics. |
| L. Reordered logical input | Equivalent state/context values presented in a different collection/query order yield identical selected skill, reason codes, and canonicalized trace. |

## 10. Implementation acceptance boundary

P7-03 through P7-14 must test strict union validation, additive
upgrade/downgrade, v1 reconstruction, all examples above, late arrival,
decision-time provenance, transaction rollback/idempotency/concurrency, mixed
API output, generator/lifecycle compatibility, typed frontend handling, and
browser explanation behavior.

This design run creates none of those tests and implements none of that code.
