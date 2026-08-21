# Phase 8 Internal Audit

**Status:** Phase 8 is `COMPLETE` on `phase/8-core-learning-agent-v1`.
External Design Review and External Implementation Review are
`APPROVED`. Phase 9 is `NOT_STARTED`.

## Final validation identity

The final implementation and browser-test HEAD validated by every command below
is `327ea5f651dc177cd0469d6dc7ec110ce8da7811`. The documentation-only audit
commit follows that validated HEAD and does not change runtime or test behavior.

## Agent contract and accounting proof

- The public Agent endpoint remains exactly
  `POST /learners/{learner_id}/writing/agent/turn`; request validation,
  learner-not-found, `practice_ready`, `await_submission`,
  `submission_conflict`, `target_achieved`, and `no_practice` paths have
  API-level coverage.
- `test_agent_stale_generated_first_submission_is_safe_conflict` advances the
  same learner after Agent generation, then proves the first stale submission
  returns HTTP 409 with `error.code=practice_conflict`, makes zero provider
  calls, does not expose `AgentStalePracticeError`, and leaves the practice
  generated with no attempt.
- Agent provider failures retain the centralized safe envelopes: timeout is
  HTTP 504/`provider_timeout`, transient/unavailable is HTTP
  503/`provider_unavailable`, and invalid response is HTTP
  502/`provider_invalid_response`. Agent persistence failure is HTTP
  503/`persistence_unavailable`; private exception text is not returned.
- PostgreSQL-backed generation tests cover all four accounting cases:
  stale-before-provider and existing-practice resolution are provider-free;
  pre-persist stale discard and a generated/resolved durable winner record a
  provider invocation.
- The provider budget has an independent gate test. Other executor bounds are
  relaxed, two provider-backed generations run, state requests a third, and the
  executor stops with `max_actions` without invoking the third call.
- Executor tests independently prove the frozen maxima of 3 mutations, 4
  observations, 2 provider-backed invocations, 1 automatic generation, and 1
  automatic completion. Exhaustion makes no extra service/provider call.
- Separate real-PostgreSQL sessions prove the stale-submission race: learner
  U/R/P becomes stale after U+1 commits, submission is rejected before provider
  work, P remains generated, and no duplicate attempt, evaluation, learning
  update, evidence, or recommendation is created. The fresh path succeeds.

## Final browser proof

The full Chromium suite exercised the next-practice branch of
`web/e2e/phase8-agent.spec.ts`:

- After targeted `practice_submission`, the dashboard's existing
  `/writing/context` resume link identified a new practice id different from
  the completed practice id.
- The test entered that persisted next practice, captured its URL, question,
  and focus, reloaded the same page, and proved the URL and practice id were
  unchanged. The Writing Task 2 question, target/focus information, and essay
  submission control remained visible.
- After explicit navigation to `/dashboard`, the server-backed resume link
  pointed to that same next practice id. A second dashboard reload preserved
  the same link.
- The completed old practice id was absent from dashboard resume actions, and
  no granular completion button was offered again.
- Learner evidence was exactly 2 before and after the dashboard reload. This is
  the concrete durable learner-state consequence and proves reload did not
  create a duplicate completion or learning update.
- The conditional terminal branch asserts the exact persisted
  `no_action` explanation and absence of the completed practice across
  dashboard reload. The deterministic final run produced a next practice, so
  the executed evidence above is the next-practice branch rather than a claim
  that the terminal branch ran.
- The older closed-loop and Phase 6 browser regressions now use the published
  Phase 8 Agent submission control and continue to prove evidence counts,
  history ordering, progress, and server-authoritative resume behavior.

## Fresh validation

All results below were produced from
`327ea5f651dc177cd0469d6dc7ec110ce8da7811` with local isolated PostgreSQL
and no live DeepSeek access.

- Backend: `python -m pytest -q --strict-markers` — **982 passed**, with one
  known Starlette/httpx deprecation warning.
- Frontend unit: `npm test` — **15 passed**.
- Frontend static/build: `npm run typecheck`, `npm run lint`, and
  `npm run build` — all passed.
- Chromium: `npm run test:e2e -- --reporter=line` — **5 passed**.
- Migration regression:
  `tests/test_practice_migrations.py` — **4 passed**. An actual isolated
  Alembic cycle `upgrade head -> downgrade 0005_planner_context_snapshot ->
  upgrade head` passed, and both `current` and `heads` reported the single
  `0006_submission_claim_recovery (head)`. The regression module includes the
  frozen legacy-upgrade/backfill proof.
- Claim recovery continues to use PostgreSQL `clock_timestamp()` under the
  row lock; no browser clock or lease calculation was introduced.

## Frozen boundaries and scope audit

Planner v1/v2 compatibility remains intact; Memory is still the Planner's
exact-tie-only input and is never supplied to the generator. The Agent continues
to use the existing deterministic generator and practice lifecycle services.

The final E2E gate changed browser tests only:
`web/e2e/phase8-agent.spec.ts`, `web/e2e/closed-loop.spec.ts`, and
`web/e2e/phase6-memory.spec.ts`. No backend runtime, schema, migration,
dependency, Agent feature, Planner/Memory semantic, PR, merge, or Phase 9 change
was made.

## Status

P8-03 through P8-13 are `COMPLETE`; P8-13 is
`INTERNAL_AUDIT_COMPLETE`. Phase 8 is `COMPLETE`.
External Design Review and External Implementation Review are
`APPROVED`. Phase 9 is `NOT_STARTED`.
