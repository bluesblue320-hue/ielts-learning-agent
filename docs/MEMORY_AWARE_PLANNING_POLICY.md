# Memory-Aware Planning Policy

## Status and version

This is the frozen Phase 7 design contract for the deterministic Writing
planner version:

```text
planner_version: writing-practice-gap-memory-v2
memory_context_version: writing-memory-aware-planning-context-v1
selection_trace_version: writing-planner-selection-trace-v1
planner_snapshot_version: writing-practice-gap-memory-v2-audit-v1
PLANNING_RECENT_PRACTICE_WINDOW: 3
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

## 2. Authoritative inputs and lazy Memory consultation

Every v2 decision begins with only the existing `LearnerSkillStateSet` decision-time snapshot and learner Writing target. The deterministic base selection completes all no-practice branches and calculates the exact maximum positive target-gap candidate set before any Memory query.

```text
State + Target
  -> deterministic base selection
     -> target_unset / cold_start / incomplete_state / target_achieved
        -> finish without MemoryAwarePlanningContext
     -> unique maximum positive gap
        -> finish without MemoryAwarePlanningContext
     -> exact maximum-gap tie
        -> build MemoryAwarePlanningContext
        -> resolve tie
```

`MemoryAwarePlanningContext` is REQUIRED only for the exact-tie branch. It is not an input to no-practice or unique-gap decisions, and an irrelevant Memory query failure must not prevent either deterministic result.

For an exact tie, the context has these planner-relevant fields for every canonical Writing skill in canonical order:

```text
trend: declining | stable | improving | insufficient_history
persistent_gap: boolean
persistent_gap_status: established | insufficient_history
recent_practice_count: non-negative integer
source_observation_ids: ordered list[LearningEvidence.id]
source_episode_ids: ordered list[LearningUpdate.id]
recent_practice_source_episode_ids: ordered list[LearningUpdate.id]
```

It additionally carries `memory_version`, `progress_version`, and `memory_context_version`. It is planner input only and MUST NOT contain `PlannerSelectionTrace`. It is not a `WritingProgressResponse`; the future builder owns a focused domain schema.

Trend and persistent-gap fields reuse the deterministic `writing-progress-v1` observation policy and provenance. The planning `recent_practice_count` does not reuse Phase 6 episode recency semantics: it is a planner-owned decision-time signal in `writing-memory-aware-planning-context-v1`, derived from the latest `PLANNING_RECENT_PRACTICE_WINDOW = 3` accepted same-learner updates ordered by `LearningUpdate.id DESC`. Its source episode ids identify that exact accepted-update window, including initial-writing entries. Phase 7 does not modify `writing-progress-v1` or public `/progress` ordering.

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

### 4.3 Planning recent practice

Retain candidates with the lowest `recent_practice_count`. For the current learner, take the latest `PLANNING_RECENT_PRACTICE_WINDOW = 3` accepted `LearningUpdate` rows by `id DESC`. Each applied targeted-practice update counts once for its actual `WritingPractice.target_skill`; an initial-writing update counts for no skill but still occupies a slot. Generated, claimed, and submitted-but-unapplied practices do not count because they have no accepted `LearningUpdate`.

This is a Phase 7 planner-context signal. It intentionally does not redefine or claim identity with Phase 6 `RECENT_PRACTICE_EPISODE_WINDOW` or public `writing-progress-v1` recency.

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

The planner output flow for an exact tie has no circular schema:

```text
State + Target
  -> base selection detects exact tie
  -> Context Builder
  -> MemoryAwarePlanningContext (input facts + provenance only)
  -> tie resolver
  -> Decision + PlannerSelectionTrace (output)
  -> Learning Application
  -> PersistedPlannerContextSnapshot (audit envelope)
```

No-practice and unique-gap branches finish before the Context Builder. All candidate lists are normalized to canonical v1 skill order. A stage is recorded only while at least two candidates remain. If a stage does not narrow, `candidates_after` MUST equal `candidates_before`; an empty attempted filter is never recorded as `candidates_after`. `canonical_priority` appears only when at least two candidates still remain and selects the first canonical skill. Stages after selection are omitted. A no-practice or unique-gap decision has no `PlannerSelectionTrace`.

## 6. Historical reconstruction and immutable audit snapshot

`PracticeRecommendation.state_snapshot` and `PracticeRecommendation.learner_target_band` already preserve the exact current-state and target inputs for a historical recommendation. The remaining Memory facts can also be reconstructed from normalized authoritative rows when bounded by the owning `LearningUpdate U`.

The current apply path acquires the learner row lock before inserting a `LearningUpdate`. Same-learner apply transactions are therefore serialized. For a committed U, the decision-time accepted set is reconstructible as committed same-learner `LearningUpdate` rows with `id <= U.id`; gaps from rolled-back or other-learner sequences are irrelevant. Future same-learner updates have later ids and are excluded.

Within that accepted set:

- restrict `LearningEvidence` to rows owned by those updates, then order each skill by `(source_created_at ASC, source_attempt_id ASC)` to reconstruct the exact trend and persistent-gap window;
- late-arriving evidence applied after U is excluded by its later owning update even when its source timestamp is older;
- order accepted updates by `LearningUpdate.id DESC`, take `PLANNING_RECENT_PRACTICE_WINDOW = 3`, and project optional actual `WritingPractice.target_skill` to reconstruct planning recency; U is necessarily the first entry;
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

## 8. Transaction, accepted-update recency, and late arrival

The application first completes deterministic base selection from state and target. It builds Memory context lazily only when the maximum-gap candidate count is greater than one. For that exact tie, context is derived inside the existing atomic transaction after the current `LearningUpdate` and evidence are flushed and state is rebuilt, but before its `PracticeRecommendation` exists. There is no provider/LLM call.

P7-05 MUST NOT call Phase 6 `list_learner_episodes()` or join `PracticeRecommendation`. It owns this minimal pre-recommendation projection:

```text
PlanningPracticeEpisode
  learning_update_id
  practice_target_skill | null
```

The query follows only `LearningUpdate -> WritingEvaluation -> WritingAttempt -> optional WritingPractice` and freezes planner accepted-learning chronology:

```text
PLANNING_RECENT_PRACTICE_WINDOW = 3
WHERE LearningUpdate.learner_id = current learner
ORDER BY LearningUpdate.id DESC
LIMIT PLANNING_RECENT_PRACTICE_WINDOW
```

Same-learner apply is serialized by the learner `FOR UPDATE` lock before `LearningUpdate` insertion, so the id order is the supported application's deterministic acceptance sequence. The just-flushed update is therefore the first entry. A current initial-writing update has null practice target but occupies a slot; a current targeted-practice update counts immediately for actual `WritingPractice.target_skill`.

`LearningUpdate.created_at` is deliberately rejected for planner recency. Its PostgreSQL `func.now()` default reflects the transaction timestamp, and a transaction that starts earlier but acquires the learner lock later can insert a higher-id accepted update with an older timestamp. A created-at LIMIT window could therefore exclude the current update under contention.

Observation chronology remains different: trend/persistent gap order evidence by `(source_created_at ASC, source_attempt_id ASC)`. Planner accepted-learning chronology orders updates by `LearningUpdate.id DESC`. Phase 7 changes neither Phase 6 L0 episode ordering nor `writing-progress-v1` public recency.

Historical reconstruction for owner U restricts to the same learner and `LearningUpdate.id <= U.id`, then orders `id DESC` and limits to the planning window. Future regression tests must prove current initial/targeted entries, differing transaction-start versus accepted-insertion order, late-arriving evidence, and exact reconstruction at U.

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
| M. Current initial episode | A just-flushed initial-writing update is first in the latest-three accepted-update id window, has null practice target, and can evict an older completed practice. |
| N. Current targeted episode | A just-flushed completed targeted-practice update is first by accepted-update id and increments the count for its actual `WritingPractice.target_skill`. |

## 11. Implementation acceptance boundary

P7-03 through P7-14 must test strict version/schema validation, the conditional snapshot matrix, all examples above, lazy Memory consultation, observation chronology, accepted-update id recency, same-learner contention where transaction-start and insertion order differ, current initial/targeted entries, exact owner-U reconstruction, late arrival, rollback/idempotency, mixed public/internal APIs, generator/lifecycle compatibility, typed frontend behavior, and browser explanation behavior.

This design run creates none of those tests and implements none of that code.
