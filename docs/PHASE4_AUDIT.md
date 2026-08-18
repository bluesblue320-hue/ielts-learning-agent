# Phase 4 Internal Audit — Adaptive Writing Practice

## Status

**Internal audit complete; second-round code review approved; final Phase 4
approval pending.** This audit records work on
`phase/4-adaptive-writing-practice`. PR #8 is the active external-review
surface. It remains open and unmerged into `master`; Phase 4 remains
`FINAL_REVIEW_PENDING` and Phase 5 is `NOT_STARTED`.

## Scope and architecture

Phase 4 implements the bounded Writing loop:

```text
PracticeRecommendation (practice)
  -> one persisted WritingPractice
  -> essay-only submission against stored question
  -> WritingAttempt + WritingEvaluation
  -> existing Phase 3 apply
  -> next PracticeRecommendation
```

Generation, inspection, submission, and completion are separate actions.
`no_practice` and cold-start outcomes do not call a generator and do not create
a practice row. The generator can decide only generated content; the persisted
Phase 3 recommendation remains the authority for learner, target skill, reason,
and decision.

## Policy and persistence evidence

- Product contract: `writing-practice-product-v1`.
- Generation policy: `writing-practice-generation-v1`.
- Preserved Phase 3 taxonomy/state/planner versions: `writing-core-v1`,
  `writing-state-ewma-v1`, and `writing-practice-gap-v1`.
- Alembic head: `0004_writing_practice`, a linear history from
  `0001_phase1 -> 0002_writing -> 0003_learning -> 0004_writing_practice`.
- The Phase 4 migration is reversible and adds only `writing_practices` plus
  `practice_recommendations(id, learner_id)` as the candidate key required for
  the composite ownership FK. It provides unique recommendation/attempt anchors,
  lifecycle checks, and RESTRICT ownership/attempt foreign keys.

## Runtime safety evidence

- Generation calls the provider outside database transactions and persists only
  successful, authority-validated output. Concurrent callers can each invoke a
  provider, but the unique recommendation anchor permits at most one durable row
  and losers resolve the winner.
- Submission locks and claims a practice before evaluating outside the
  transaction. Finalization atomically creates the Phase 2 attempt/evaluation,
  attaches the attempt, and marks the practice submitted. Normalized provider
  failures reset the owned claim without orphan writing records.
- A recoverable SQLAlchemy finalization failure rolls back the complete atomic
  transaction and then performs a short `FOR UPDATE` cleanup transaction. It
  resets only the still-owned matching claim token to `generated`; it never
  clears another caller's claim. If cleanup cannot reach the database, the
  normalized persistence failure is returned and the abandoned claim remains.
- Completion reuses the existing idempotent Phase 3 application service and
  returns a next recommendation; it never generates another practice.

## Validation evidence

All validation used the isolated PostgreSQL Docker `test-db` and deterministic
fakes; no DeepSeek credential or live provider call was required.

| Area | Evidence |
| --- | --- |
| Generator runtime | P4-08 focused tests: 60 passed |
| Generation service and migration | P4-09 focused PostgreSQL tests: 12 passed |
| Submission claim/finalization | P4-10 focused PostgreSQL tests: 19 passed |
| Completion/replan | P4-11 service plus regression tests: 16 passed |
| API lifecycle | P4-12 API/service tests: 32 passed, one deprecation warning |
| Concurrency | P4-13 isolated PostgreSQL tests: 15 passed; two concurrent submissions yielded one evaluator, one attempt, one evaluation, and one linked practice |
| Latest PR CI / isolated PostgreSQL validation | `796 passed, 1 warning` (`StarletteDeprecationWarning` for `httpx`/`TestClient`) |

The latest successful PR CI result is `796 passed, 1 warning`, using a fresh
Docker test-image build and isolated test database.

## External-review repair evidence

The follow-up repairs add centralized Phase 4 persistence/authority error
normalization (`503 persistence_unavailable` and `502
provider_invalid_response`), expanded public lifecycle API coverage, the
recoverable finalization claim cleanup described above, and a typed
`decision_type = practice` generation request plus `thinking_mode` protocol
property. The prescribed focused Phase 4 Docker/PostgreSQL/API/migration/
concurrency suite passed **46 passed, 1 warning**.

## Commit checkpoints

| Nodes | Commit |
| --- | --- |
| P4-01 | `2713de7 docs: record Phase 4 baseline transition` |
| P4-02 | `9546bb1 docs: define adaptive practice product contract` |
| P4-03 | `7e3c881 docs: freeze writing practice generation policy` |
| P4-04 | `7eb5ac2 feat: add writing practice schemas` |
| P4-05 | `ccd03b6 feat: add writing practice persistence models` |
| P4-06 | `e9c7a03 feat: add writing practice migration` |
| P4-07 | `8cf3523 feat: define practice generator contract` |
| P4-08 | `31ec75f feat: implement practice generation runtime` |
| P4-09 | `fc5c320 feat: add practice generation service` |
| P4-10 | `b9ea27d feat: add claimed practice submission` |
| P4-11 | `4d003f7 feat: add practice completion replan service` |
| P4-12 | `16eebc7 feat: add writing practice lifecycle APIs` |
| P4-13 | `4461f6f test: prove practice concurrency invariants` |
| P4-14 | `8e7f37a test: validate complete adaptive writing loop` |
| P4-15 | `983ea78 docs: document adaptive writing practice loop` |

## Scope and security review

No secrets were added. Configuration remains environment-based. No Phase 2
scoring/rubric or Phase 3 state/planner policy was redesigned. No frontend,
memory/RAG, Redis, background job system, multi-agent runtime, additional IELTS
skill, PR, merge, force-push, or Phase 5 work was introduced.

## Known limitations and external-review focus

- Generation is exactly-once only at durable persistence: concurrent first
  callers may duplicate provider invocation before unique-row winner resolution.
- A hard process crash or database-unavailable claim-cleanup can still leave an
  abandoned `submission_in_progress` claim. There is no automatic recovery,
  lease, or claim stealing in v1; recovery requires an explicit future product
  decision.
- The product band and provider feedback are application behavior, not a claim
  of official IELTS score equivalence.

PR #8 has completed second-round code review. The final Phase 4 approval and
merge authorization remain outside this audit; the PR must remain unmerged
until that explicit authorization is given.
