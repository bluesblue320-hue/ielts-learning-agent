# Phase 3 Final Audit — Learner State & Adaptive Planning

**Status:** PHASE 3 = FINAL_REVIEW_PENDING (external final review in progress)
**Branch:** `phase/3-learner-state-planning`
**Starting review baseline:** `b4b6e85`
**P3-14 implementation HEAD:** `f9e8143`
**Initial P3-15 audit commit:** `3e1e11b`
**Audit created:** by node `P3-15`

> Historical note: WorkBuddy's internal P3-15 audit initially marked the Phase
> 3 implementation complete. The branch is now under external final review;
> `P3-15` is `VERIFYING` / `FINAL_REVIEW_FIXING` and Phase 3 status is
> `FINAL_REVIEW_PENDING` until that review and the pull-request CI gate
> complete. Final-review corrections are recorded in subsequent branch
> history.

---

## 1. Node status

| Node | Status | Commits |
| --- | --- | --- |
| P3-01 — Phase 3 baseline | COMPLETE | `cd00659` |
| P3-02 — Writing skill taxonomy & state policy | COMPLETE | `ad6db55` |
| P3-03 — Learner / evidence / state schemas | COMPLETE | `d136a3d`, `c7f1790` |
| P3-04 — Persistence models | COMPLETE | `dc814c7`, `be7ace9` |
| P3-05 — Alembic migration | COMPLETE | `1bdf17c`, `b4b6e85` |
| P3-06 — Writing evidence extraction | COMPLETE | `2b78be2` |
| P3-07 — Learner state update engine | COMPLETE | `ec6a66d` |
| P3-08 — Practice planning policy | COMPLETE | `b5f93a4`, `8b90cbe`, `2e94d61` |
| P3-09 — Practice planner | COMPLETE | `de15876` |
| P3-10 — Learning update application service | COMPLETE | `6568c4a` |
| P3-11 — Learner & learning APIs | COMPLETE | `3e36426` |
| P3-12 — Concurrency / failure / idempotency | COMPLETE | `609e9e7` |
| P3-13 — Consolidated validation | COMPLETE | `a77719b` |
| P3-14 — Docker & documentation | COMPLETE | `f9e8143` |
| P3-15 — Final phase audit | VERIFYING / FINAL_REVIEW_FIXING | `3e1e11b` + final-review commits |

## 2. Frozen policy versions

- Skill taxonomy: `writing-core-v1` — exactly four canonical skills
  (`task_response`, `coherence_and_cohesion`, `lexical_resource`,
  `grammatical_range_and_accuracy`).
- State policy: `writing-state-ewma-v1` — `S1 = X1`;
  `Sn = 0.5 * Xn + 0.5 * S(n-1)` in exact Decimal; alpha frozen at `0.5`;
  single final quantization to `0.01` with `ROUND_HALF_UP`.
- Planner version: `writing-practice-gap-v1` — largest positive target gap,
  frozen tie-break priority, threshold `MIN_ESTABLISHED_EVIDENCE_COUNT = 3`.

## 3. Canonical order and replay proof

Canonical cross-evaluation order is frozen as `WritingAttempt.created_at ASC`
then `WritingAttempt.id ASC`. The immutable source values are copied into
`LearningEvidence` (`source_created_at`, `source_attempt_id`); arrival order,
transaction order, insertion order, and evidence primary keys never control
state. Every apply rebuilds all four skill states from the complete accepted
evidence set.

Final evidence (real PostgreSQL, `tests/test_phase3_consolidated.py` and
`tests/test_learning_concurrency.py`):

```text
A = 6.0, B = 7.0  (task_response)
sequential A -> B        : 6.50
late arrival  B -> A     : 6.50
concurrent schedules     : 6.50
canonical replay(A, B)   : 6.50
evidence_count           : 2
last evidence            : B (canonical newest, source_attempt_id 101)
```

All three application schedules produce the same final materialized state
equal to canonical replay for every skill.

## 4. Determinism and precision

- `ewma_estimate` retains exact Decimal intermediates (e.g. `6.625`,
  `6.5625`); only the final materialized value is quantized once to 0.01 with
  `ROUND_HALF_UP` (`6.63`, `6.56`).
- Repeated extraction/planner/replay runs are byte-identical; no
  `datetime.now()` (except application-maintained state-row `updated_at`),
  `uuid`, `random`, or request-local state participates in canonical values.
- Planner decisions are input-order independent and carry the full
  decision-time state snapshot.

## 5. Practice / no_practice behavior

Every successful apply persists exactly one `PracticeRecommendation`:

- `practice` — largest positive target gap, frozen tie priority
  (`task_response` first), qualifiers `priority_tiebreak` and
  `insufficient_evidence` exactly when applicable; `current_estimate` equals
  the snapshot estimate and is strictly below the target.
- `no_practice` — `target_achieved` (optionally with `insufficient_evidence`),
  `cold_start`, `incomplete_state`, or `target_unset`; `target_skill` null.

Both outcomes persist exactly one auditable row (DB `UNIQUE
(learning_update_id)` + frozen reason-sequence checks).

## 6. Atomicity, idempotency, ownership

- One successful transaction: `1 LearningUpdate`, `4 LearningEvidence`,
  `4 LearnerSkillState`, `1 PracticeRecommendation`. Any stage failure rolls
  back all Phase 3 writes (verified with injected mid-transaction and
  extraction failures).
- Idempotency: same learner + same evaluation returns the existing logical
  result (`reused=true`), no duplicate rows, counts and revisions unchanged.
- Cross-owner: reusing an evaluation owned by another learner raises an
  explicit conflict (409 `evaluation_conflict`); the database `UNIQUE
  (writing_evaluation_id)` on `learning_updates` is the global ownership anchor.
- Phase 2 `writing_attempts` / `writing_evaluations` rows are never modified
  by Phase 3 applies (verified).

## 7. Concurrency correctness

Per-learner row lock (`SELECT ... FOR UPDATE` on the learner) serializes
applications to the same learner; the `writing_evaluation_id` unique constraint
and under-lock idempotency re-check prevent double application. Real
PostgreSQL tests prove, for canonical source order `A` (older) then `B`
(newer) with `task_response` 6.0 and 7.0:

- sequential `A -> B` → 6.50;
- late arrival `B -> A` → 6.50;
- **controlled concurrent A-first** (A explicitly owns the learner lock, then
  B applies) → completion order `[A, B]`, final 6.50;
- **controlled concurrent B-first** (B explicitly owns the learner lock, then
  A applies) → completion order `[B, A]`, final 6.50;
- canonical replay(A, B) → 6.50;
- all four schedules are equal to canonical replay for every skill, with
  `evidence_count = 2`, `revision = 2`, and canonical last evidence = B;
- concurrent same learner + same evaluation → exactly one logical application
  (1 update, 4 evidence, 4 states, 1 recommendation) with no duplicate
  revision/evidence effects;
- no deadlocks observed across repeated race rounds.

## 7a. Safe persistence failure boundary

Unexpected Phase 3 database failures — database read/write failure, unexpected
constraint violations that are not the accepted idempotency race, and general
SQLAlchemy/PostgreSQL failures — are reported as `LearningPersistenceError`
and mapped by the APIs to HTTP **503** `persistence_unavailable` with the
stable safe error contract. No raw SQL, constraint names, exception text,
database URLs, or source contents leak. Only the accepted idempotency
uniqueness violation (`uq_learning_update_writing_evaluation_id`) enters
duplicate-resolution behavior; expected domain outcomes (404 not found, 409
cross-owner, 422 invalid source) remain distinct.

## 8. Migration

- Single linear Alembic head: `0003_learning` (`base -> 0001_phase1 ->
  0002_writing -> 0003_learning`).
- Upgrade `0002 -> 0003`, downgrade `0003 -> 0002`, re-upgrade all verified on
  real PostgreSQL; downgrade removes only the five Phase 3 tables.
- Model ↔ migration drift: `compare_metadata(Base.metadata)` returns no
  differences after upgrade.
- Five tables: `learners`, `learning_updates`, `learning_evidence`,
  `learner_skill_states`, `practice_recommendations`; JSONB `reason_codes` /
  `state_snapshot`; composite ownership FKs; canonical replay index.

## 9. Test results (final review)

| Run | Result |
| --- | --- |
| Full pytest (isolated PostgreSQL, host) | **705 passed, 1 warning** |
| Full pytest (containerized, Docker Compose test profile) | **705 passed, 1 warning** |
| Migration suites | 11 passed |
| Phase 3 contract suites | 200+ passed |
| Concurrency suites (incl. controlled A-first / B-first) | all passed |
| Persistence-failure + safe-503 API suites | all passed |
| Required PostgreSQL integration tests | executed, none skipped |

The single warning is the recorded Starlette `httpx` deprecation. No live
provider call occurs; no DeepSeek credential is required.

## 10. Security / secrets / scope review

- No `.env` committed; no secrets in the repository; environment-based
  configuration unchanged.
- Forbidden-scope review: no LangGraph/LangChain/agent runtime, no RAG/
  pgvector, no Redis/Celery/Kafka, no frontend, no auto lesson/exercise
  generation, no LLM-based state update or planning, no Speaking/Reading/
  Listening. Phase 3 remains FastAPI + SQLAlchemy + PostgreSQL + deterministic
  domain logic.
- APIs expose only safe error contracts; no raw exception text leaks. Phase 3
  database failures map to 503 `persistence_unavailable` with no SQL,
  constraint, or exception details exposed.

## 11. Documentation truth

`README.md`, `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/LOCAL_DEVELOPMENT.md`,
`docs/PHASE3_GRAPH.md`, `docs/WRITING_STATE_POLICY.md`,
`docs/PRACTICE_PLANNING_POLICY.md` describe only implemented behavior and
clearly separate implemented Phase 3 from future phases.

## 12. Known limitations

- The planner optimizes a single next practice target; multi-skill scheduling
  and content generation are future work.
- Evidence is restricted to the four Writing criterion bands; speaking,
  reading, and listening workflows are not implemented.
- The state policy is sequence-based EWMA only; wall-clock decay and
  confidence are intentionally absent (frozen policy).

## 13. Recommendation for the next phase

Begin Phase 4 with learner-facing adaptive practice content driven by the
persisted `PracticeRecommendation` decisions, and extend the deterministic
state/planning path to Speaking, Reading, and Listening using the same frozen
policy discipline.

---

PHASE 3 = FINAL_REVIEW_PENDING — awaiting external review and PR CI gate.
Phase 4 has not started.
