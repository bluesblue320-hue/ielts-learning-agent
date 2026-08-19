# Memory-Aware Planning Policy

## Status and version

This is the frozen Phase 7 design contract for the deterministic Writing
planner version:

```text
planner_version: writing-practice-gap-memory-v2
memory_context_version: writing-memory-aware-planning-context-v1
selection_trace_version: writing-planner-selection-trace-v1
planner_snapshot_version: writing-practice-gap-memory-v2-audit-v1
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
`memory_context_version`. `MemoryAwarePlanningContext` is planner input only
and MUST NOT contain `PlannerSelectionTrace`. It is not a
`WritingProgressResponse`; the public response has unrelated presentation/read-
model fields and must not become a write-path dependency. The future context
builder owns a focused domain schema and uses Phase 6's frozen pattern and
episode-window primitives.

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

## 5. Reason codes and planner output trace

Reason codes retain their v1 meaning and allowed ordering:

- Every normal v2 practice begins with `largest_target_gap`.
- Add `priority_tiebreak` if and only if the final `canonical_priority` stage actually narrows an unresolved tie.
- Add `insufficient_evidence` exactly when the selected state snapshot has fewer than three evidence rows, as in v1.
- Memory stages that narrow candidates add no new reason code.

`PlannerSelectionTrace` is planner output, separate from `MemoryAwarePlanningContext`. It exists only for a practice decision that began with an exact maximum-gap tie and has this strict shape:

```text
trace_version: writing-planner-selection-trace-v1
initial_max_gap_candidates: ordered canonical skill list
stages: ordered list of {
  stage: persistent_gap | trend | recent_practice | canonical_priority
  candidates_before: ordered canonical skill list
  candidates_after: ordered canonical skill list
  narrowed: boolean
}
selected_skill: canonical skill
```

The planner flow has no circular input/output schema:

```text
Context Builder
  -> MemoryAwarePlanningContext (input facts + provenance only)
  -> Planner v2
  -> Decision + PlannerSelectionTrace (output)
  -> Learning Application
  -> PersistedPlannerContextSnapshot (audit envelope)
```

All candidate lists are normalized to canonical v1 skill order. A stage is recorded only while at least two candidates remain. If a stage does not narrow, `candidates_after` MUST equal `candidates_before`; an empty attempted filter is never recorded as `candidates_after`. `canonical_priority` appears only when at least two candidates still remain and selects the first canonical skill. Stages after selection are omitted. A no-practice or unique-gap decision has no `PlannerSelectionTrace`.

## 6. Historical reconstruction and immutable audit snapshot

`PracticeRecommendation.state_snapshot` and `PracticeRecommendation.learner_target_band` already preserve the exact current-state and target inputs for a historical recommendation. The remaining Memory facts can also be reconstructed from normalized authoritative rows when bounded by the owning `LearningUpdate U`.

The current apply path acquires the learner row lock before inserting a `LearningUpdate`. Same-learner apply transactions are therefore serialized. For a committed U, the decision-time accepted set is reconstructible as committed same-learner `LearningUpdate` rows with `id <= U.id`; gaps from rolled-back or other-learner sequences are irrelevant. Future same-learner updates have later ids and are excluded.

Within that accepted set:

- restrict `LearningEvidence` to rows owned by those updates, then order each skill by `(source_created_at ASC, source_attempt_id ASC)` to reconstruct the exact trend and persistent-gap window;
- late-arriving evidence applied after U is excluded by its later owning update even when its source timestamp is older;
- order the accepted update episodes by `(LearningUpdate.created_at DESC, LearningUpdate.id DESC)` and project their optional actual `WritingPractice.target_skill` to reconstruct the historical recent-practice window;
- use U's recommendation target snapshot and state snapshot rather than present learner values.

Therefore historical context reconstruction is possible; recomputing today's unbounded progress is merely the wrong reconstruction query. Phase 7 still chooses a persisted snapshot as an intentional immutable decision-time audit record. This avoids making routine product explanations depend on replaying historical query semantics, makes the exact planner input/output self-contained, and permits direct comparison against authoritative-row reconstruction during audit. Normalized rows remain authoritative evidence and a verification source; the stored snapshot is authoritative for what the planner consumed and emitted at that decision.

P7-04 must add one nullable JSONB column to `practice_recommendations`:

```text
planner_context_snapshot JSONB NULL
```

When present it validates as `PersistedPlannerContextSnapshot`, containing exactly:

```text
snapshot_version: writing-practice-gap-memory-v2-audit-v1
memory_context: MemoryAwarePlanningContext
selection_trace: PlannerSelectionTrace
```

Presence is minimal and conditional:

```text
writing-practice-gap-v1
  -> NULL
writing-practice-gap-memory-v2 + no_practice
  -> NULL
writing-practice-gap-memory-v2 + practice + unique maximum gap
  -> NULL
writing-practice-gap-memory-v2 + practice + exact maximum-gap tie
  -> REQUIRED PersistedPlannerContextSnapshot
```

The migration accepts only NULL or a JSON object at the database layer; strict Pydantic/domain validation enforces the versioned envelope and conditional presence rule. A missing snapshot for a persisted v2 exact-tie practice is an invariant violation and must not be silently repaired from current progress. No new table, generic planner-history table, v1 backfill, or historical rewrite is permitted.

## 7. Internal schema and public product boundaries

The current `PracticeRecommendationDecision` is historically v1-specific. A future implementation preserves a strict v1 decision and adds a strict v2 decision, discriminated by `planner_version`. The planner application result may carry an optional `PlannerSelectionTrace`, and persistence reconstruction may carry an optional `PersistedPlannerContextSnapshot`; neither makes the full audit envelope part of the normal public recommendation object.

Internal persisted/audit representation contains the full context, provenance ids, and trace only when section 6 requires it. Public product representation contains the existing recommendation decision fields, `planner_version`, and a safe deterministic `planning_explanation` for a relevant v2 exact tie. That explanation is derived from the persisted historical trace, never current progress, and may expose only semantic factors: equal current maximum gap, persistent-gap tie-break, trend tie-break, lower recent-practice count, or canonical fallback.

Normal product fields MUST NOT expose source observation/episode ids or the raw JSONB audit envelope. If episode detail later needs a developer/audit provenance surface, P7-09 must define a distinct audit representation rather than equating the public recommendation with `PersistedPlannerContextSnapshot`.

Apply, completion, history, and context APIs must reconstruct the correct v1/v2 public decision. Practice generation remains version-agnostic: it consumes the persisted target skill and existing generator request fields and never receives Memory context, trace, or the audit envelope.

## 8. Transaction, pre-recommendation recency, and late arrival

The v2 context is derived inside the existing atomic learning-application transaction after the new `LearningEvidence` rows and current `LearningUpdate` are flushed and all four states are canonically rebuilt, but before its `PracticeRecommendation` exists. There is no provider/LLM call in this transaction.

P7-05 MUST NOT call Phase 6 `list_learner_episodes()` for transaction-time recency. That query inner-joins `PracticeRecommendation`, so it omits the in-flight update before recommendation persistence. Instead P7-05 owns a minimal pre-recommendation projection:

```text
PlanningPracticeEpisode
  learning_update_id
  created_at
  practice_target_skill | null
```

Its query follows only:

```text
LearningUpdate
  -> WritingEvaluation
  -> WritingAttempt
  -> optional WritingPractice
```

It has no `PracticeRecommendation`, route, or `WritingProgressResponse` dependency. It orders by `LearningUpdate.created_at DESC, LearningUpdate.id DESC`, applies `RECENT_PRACTICE_EPISODE_WINDOW = 3`, and includes the just-flushed current update immediately. A current initial-writing update has null practice target but still occupies a window slot and can push an older practice out. A current completed targeted-practice update counts against the actual `WritingPractice.target_skill`.

Trend and persistent gap use `(source_created_at ASC, source_attempt_id ASC)`, so newly inserted evidence participates immediately even if it describes an older attempt. Late arrival can change the new decision's context but cannot change any stored earlier exact-tie snapshot. Future regression tests must prove both current episode window cases, the no-recommendation query boundary, late arrival, and equivalence between decision-time facts and bounded historical reconstruction.

## 9. V2 activation and coexistence

After Phase 7 implementation is explicitly activated, every newly applied Writing evaluation uses `writing-practice-gap-memory-v2`. Historical rows remain v1. No request parameter selects a planner version, no runtime feature flag is introduced in Phase 7, and no historical `planner_version`, reason, or decision row is rewritten. Idempotent replay returns the already-persisted version.

## 10. Normative examples

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
| J. Late arrival | An older source attempt is applied after newer evidence; it enters canonical trend order immediately. If the new decision has an exact tie, it snapshots that bounded context; earlier snapshots stay unchanged. |
| K. Historical v1 | A row with `writing-practice-gap-v1` and NULL context reconstructs with the original v1 model and original reason semantics. |
| L. Reordered logical input | Equivalent state/context values presented in a different collection/query order yield identical selected skill, reason codes, and canonicalized trace. |
| M. Current initial episode | A just-flushed initial-writing update occupies one latest-three recency slot with null practice target and can evict an older completed practice. |
| N. Current targeted episode | A just-flushed completed targeted-practice update occupies a slot and increments the count for its actual `WritingPractice.target_skill`. |

## 11. Implementation acceptance boundary

P7-03 through P7-14 must test strict union validation, additive
upgrade/downgrade, v1 reconstruction, all examples above, late arrival,
decision-time provenance, the pre-recommendation initial/targeted recency cases,
transaction rollback/idempotency/concurrency, mixed
API output, generator/lifecycle compatibility, typed frontend handling, and
browser explanation behavior.

This design run creates none of those tests and implements none of that code.
