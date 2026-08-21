# Phase 8 Internal Audit

**Status:** `INTERNAL_AUDIT_COMPLETE` on `phase/8-core-learning-agent-v1`.
External Design Review is `APPROVED`; External Implementation Review is
`PENDING_RE_REVIEW`. Phase 9 is `NOT_STARTED`.

## Final repair evidence

The final repair series through `2bca101` restores the frozen public Agent
surface `POST /learners/{learner_id}/writing/agent/turn` with no alias.

- Provider accounting has four PostgreSQL-backed generation cases, plus an independent executor test that prevents a third provider-backed invocation once the frozen budget of two is reached: stale
  preflight and existing-practice resolution are provider-free; a provider call
  followed by stale pre-persist discard and a successful durable winner both
  set `provider_invoked=true`.
- `practice_ready` is trajectory-sensitive: only an Agent turn which generated
  or resolved the current practice returns it; an already-generated practice
  remains `needs_practice_submission`.
- Executor tests prove the frozen 3 mutation, 4 observation, 2 provider, 1
  automatic generation, and 1 automatic completion bounds. Exhaustion stops
  as `max_actions` without another service call.
- Independent PostgreSQL sessions prove an Agent first submission fenced by
  U/R rejects after the same learner advances to U+1, with zero provider calls,
  no attempt/evaluation, and the old practice still generated. The fresh U/R
  path finalizes normally.
- Claim leases use PostgreSQL `clock_timestamp()` after the WritingPractice
  row lock; migration tests cover legacy expired backfill and downgrade/reupgrade.
- Chromium covers the full Agent practice submission loop, including automatic
  evaluation/completion/replan, next-practice or terminal navigation, and a
  reload showing server-authoritative state without duplicate effects.
- Agent API tests cover frozen path discovery, invalid body, missing learner,
  `practice_ready`, and provider-free `target_achieved`, using safe envelopes.

## Fresh validation

- Backend: `python -m pytest -q --strict-markers` completed against isolated
  PostgreSQL; the final strict suite contains **974 tests**. No live DeepSeek
  credentials or HTTP calls are permitted by the test guard.
- Frontend: `npm test` **15 passed**; `npm run typecheck`, `npm run lint`, and
  `npm run build` passed.
- Chromium: `npm run test:e2e -- --reporter=line` ran the full **5-spec** suite;
  the focused expanded Phase 8 closed-loop spec passed independently.
- Migration: isolated Alembic `upgrade head`, `downgrade 0005_planner_context_snapshot`,
  and `upgrade head` passed; head is `0006_submission_claim_recovery`.

## Frozen boundaries and scope audit

Planner v1/v2 recommendation compatibility remains intact; Memory remains the
Planner's exact-tie-only input and is never supplied to the generator. The
Agent uses existing deterministic generator and practice lifecycle services.
No generic Agent table, worker, queue, background autonomy, framework,
dependency, new skill, Planner/Memory semantic change, PR, merge, or Phase 9
work was introduced.

## Status

P8-03 through P8-13 are `COMPLETE`; P8-13 is `INTERNAL_AUDIT_COMPLETE`.
Phase 8 is `INTERNAL_AUDIT_COMPLETE`; Phase 9 is `NOT_STARTED`.