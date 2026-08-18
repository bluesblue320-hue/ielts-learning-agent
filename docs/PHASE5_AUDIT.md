# Phase 5 Internal Final Audit

**Status:** INTERNAL_AUDIT_COMPLETE — external review pending.

P5-01 through P5-15 are complete on `phase/5-web-product-mvp`. The Chinese-first Next.js client remains presentation-only; FastAPI owns all evaluation, state, planning, practice lifecycle, and persistence, and PostgreSQL remains authoritative.

## P5-15 evidence

- `python -m pytest -q --strict-markers`: **797 passed, 1 warning**
- `npm --prefix web run lint`: passed
- `npm --prefix web run typecheck`: passed
- `npm --prefix web test`: **4 passed**
- `npm --prefix web run build`: passed
- `npm --prefix web run test:e2e`: **1 passed** using Chromium, Next.js, FastAPI, deterministic `FakeProvider`, deterministic `FakePracticeGenerator`, and isolated PostgreSQL.

The browser test proves create learner, initial evaluation/apply/state read, persisted recommendation generation, read-only practice question, essay-only submission, persisted practice evaluation retrieval, complete/replan, updated state rendering, and stop before automatic next-practice generation.

The P5-04 fields (`evaluation_id`, `recommendation_id`, `next_recommendation_id`) and practice-scoped persisted evaluation endpoint are exercised by that loop. Browser storage remains limited to the four frozen presentation fields and excludes essays, evaluations, provider data, submission tokens/fingerprints, and secrets.

No live DeepSeek call is present in E2E or CI. CI now installs Chromium and enforces backend, frontend, production-build, and browser E2E gates. Phase 6 is not started.
## External review repair

The practice workspace now reloads authoritative lifecycle state: submitted practices restore persisted evaluations and Complete without an editable resubmission UI; in-progress practices expose only a safe recheck. Central Chinese skill, planner-reason, and safe API-error presentation is tested. Browser E2E proves submit → reload → evaluation restoration and learner-state/recommendation rendering after apply and completion.