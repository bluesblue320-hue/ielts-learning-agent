# Phase 8 Internal Audit

**Status:** `INTERNAL_AUDIT_COMPLETE` on `phase/8-core-learning-agent-v1`.
External Design Review authorized implementation; External Implementation Review
is pending. Phase 9 is not started.

## Scope reconciled

- P8-03 defines the strict `writing-core-learning-agent-v1` request, response,
  observation, stop, and safe-trace schemas.
- P8-04 adds only `writing_practices.submission_claimed_at` through Alembic
  revision `0006_submission_claim_recovery`. PostgreSQL time owns the
  300-second lease; legacy in-progress claims are backfilled expired, and the
  exact lifecycle metadata matrix is enforced.
- P8-05 through P8-09 provide provider-free accepted-update observation,
  direct-service tools, pure selection, a bounded executor, and the single
  `POST /learners/{learner_id}/writing/agent/turn` surface. Factories remain lazy and
  honor dependency overrides, so provider-free branches never resolve provider
  settings.
- P8-10 through P8-12 preserve the granular initial Writing and practice paths,
  add Chinese-first safe Agent status/step presentation, and cover the bounded
  browser flow.
- P8-11 proves legacy backfill/reclaim, exact-fingerprint conflict, old-token
  rejection, provider/finalization cleanup, concurrent single durable effects,
  and submitted historical replay without provider work.

## Evidence

- `494e5bf test: harden Phase 8 recovery replays`
- `56b6acf test: validate Phase 8 agent lifecycle`
- Full backend suite: `964 passed, 1 warning` with isolated PostgreSQL.
- Frontend: `npm test` (15 passed), `npm run typecheck`, `npm run lint`, and
  `npm run build` all passed.
- Chromium: `npm run test:e2e -- --reporter=line` passed all 5 specs against
  the dedicated disposable `ielts_e2e_test` database.

## Boundaries and known limitation

No generic Agent-run table, worker, queue, background autonomy, Agent
framework, Planner/Memory semantic change, new IELTS skill, dependency, or
Phase 9 work was introduced. The durable database effects are at-most-once;
physical exactly-once provider work after a process crash remains impossible
without a provider idempotency receipt, as frozen by the policy.

## Review handoff

The implementation is ready for External Implementation Review. Do not create a
PR, merge the branch, or begin Phase 9 as part of this phase.