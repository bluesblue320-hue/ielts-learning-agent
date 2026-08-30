# IELTS Learning Agent

IELTS Learning Agent is the foundation of a long-term adaptive IELTS learning
system. The target product will maintain structured learner state, evaluate
learning outcomes, retain useful learning history, and select future practice;
it is not intended to be only a chatbot or a thin LLM wrapper.

## Current status

**Phase 1 = COMPLETE. Phase 2 = COMPLETE. Phase 3 = COMPLETE. Phase 4 = COMPLETE. Phase 5 = COMPLETE and MERGED through PR #9 (`feat: deliver Phase 5 Chinese-first web MVP`), merge commit `56498c3d59aad4ae645c5b78c6b6dc41bec62bcf`. Phase 6 = COMPLETE and MERGED through PR #10 (`feat: deliver Phase 6 hierarchical learning memory & longitudinal progress`), merge commit `b8e419d8c146c921539f4654b5aeb0b56ed6f425`.**

**Phase 7 = COMPLETE and MERGED through PR #11**, merge commit
`cbf1ebabc87ec490f74957d1327037dae4242381`; both external reviews and CI
are approved/successful.

**Phase 8 = COMPLETE and MERGED through PR #12**, merge commit
`4739bca53ebcae96f10bca256e3568a644f2fef4`. The bounded Writing-only
Core Learning Agent v1 is available through
`POST /learners/{learner_id}/writing/agent/turn`.

**Phase 9 = COMPLETE and MERGED through PR #13**, merge commit
`75a667ff4ce16b79e7d4ba517081e1bd3d96fd57`. Both External Design Review and
External Implementation Review are `APPROVED`. Phase 9 delivers the static
`ielts-writing-knowledge-v1` snapshot, deterministic structured retrieval,
provider-free grounded guidance, knowledge-grounded practice generation v2, and
source/citation UX.

**Phase 10 = COMPLETE and MERGED through PR #14**, merge commit
`c7a5f991df9c556408295d01194f1f17c13653b5`. Its frozen
`writing-eval-calibration-v1` contract, canonical 11-case deterministic
runtime, structured reports, CI gate, P10-18 internal audit, and external
reviews are complete.

**Current phase: Phase 11 — Structured Wiki Knowledge v1.** Phase 11 is STARTED.
P11-00 is COMPLETE; Phase 11 Graph Review is APPROVED; P11-01 is COMPLETE; its
External Audit Review is APPROVED. P11-02 is COMPLETE; Phase 11 External Design
Review is APPROVED. P11-03 through P11-13 are COMPLETE. Phase 11 Milestone
Review is APPROVED. P11-09 through P11-15 are COMPLETE, and P11-16 is
`INTERNAL_AUDIT_COMPLETE`. External Implementation Review is
CHANGES_REQUESTED; PR validation and merge authorization remain blocked, so
Phase 11 is NOT COMPLETE.

Phase 7 connects authoritative current learner state and longitudinal Writing
Memory to deterministic Planner v2. Memory is consulted only for exact
maximum-gap ties, using persistent gap → trend → planning recent practice →
canonical priority; historical `writing-practice-gap-v1` remains supported and
frozen.

Phase 3 adds a
complete deterministic learner-state path on top of the Phase 2 Writing
pipeline:

- a versioned learner-state taxonomy (`writing-core-v1`) and EWMA state policy
  (`writing-state-ewma-v1`) with exact Decimal replay, single final
  quantization, and canonical `WritingAttempt.created_at / id` ordering;
- learner creation, four-skill materialized state, and atomic application of a
  persisted Writing evaluation (`1 update, 4 evidence rows, 4 state rows,
  1 planning decision` per successful apply), with idempotent replay and
  explicit cross-owner conflict;
- a deterministic practice planner (`writing-practice-gap-v1`) that selects the
  largest positive target-gap skill, or records a `no_practice` decision
  (cold start, incomplete state, target achieved, target unset);
- REST APIs to create learners, inspect state, and apply evaluations, plus
  concurrency-hardened application (per-learner row lock + unique constraints)
  proven on real PostgreSQL;
- the reversible `0003_learning` Alembic migration materializing all Phase 3
  persistence models.

The Phase 3 execution record is [docs/PHASE3_GRAPH.md](docs/PHASE3_GRAPH.md).
Semantic retrieval, generic RAG, and Speaking, Reading, and Listening workflows
remain outside the implemented system. Phase 9 grounding is deterministic and
Writing Task 2–only.

## Technology stack

| Area | Implemented stack |
| --- | --- |
| Backend | Python 3.12+, FastAPI, Pydantic v2 |
| Persistence | PostgreSQL, SQLAlchemy 2.x, Alembic |
| Learner state | Deterministic EWMA replay + frozen policy constants |
| Planning | Deterministic target-gap planner (no LLM) |
| Frontend | Next.js, TypeScript, Tailwind CSS |
| Testing | pytest, httpx, Playwright, isolated PostgreSQL integration |
| Infrastructure | Docker, Docker Compose |

## Quick start with Docker

Requirements: Docker Desktop or Docker Engine with Docker Compose.

1. Copy `.env.example` to `.env`.
2. Replace every placeholder database password in `.env`. Set
   `IELTS_DEEPSEEK_API_KEY` only for real writing evaluations; health checks and
   deterministic tests do not require it. Never commit `.env`.
3. Build and start PostgreSQL, migrations, and the API:

```bash
docker compose up -d --build --wait
```

4. Check the API:

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

5. Run the complete test suite in the test image:

```bash
docker compose --profile test run --rm --build test
```

The test profile starts a separate, non-persistent `test-db` service. Pytest and
its Alembic downgrade/re-upgrade checks never connect to the development `db`.

With `IELTS_TEST_DATABASE_URL` pointing to that isolated database, run the
provider-free Phase 10 deterministic Eval gate locally with:

```bash
python -m app.eval.gate
```

This command never invokes Live Calibration or a real provider and requires no
provider key. It is the dedicated CI gate; the complete backend suite remains a
separate validation step.

6. Stop services while preserving development data:

```bash
docker compose down
```

See [local development](docs/LOCAL_DEVELOPMENT.md) for database-only commands,
local Python setup, migrations, cleanup, and Windows Docker troubleshooting.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health/live` | Process liveness; never requires PostgreSQL |
| `GET` | `/health/ready` | PostgreSQL readiness; returns `503` when unavailable |
| `POST` | `/writing/evaluate` | Validate, evaluate, and atomically persist one Writing Task 2 submission |
| `POST` | `/learners` | Create a learner with a Writing target band |
| `GET` | `/learners/{learner_id}/state` | Inspect the four-skill materialized learner state |
| `POST` | `/learners/{learner_id}/writing/evaluations/{evaluation_id}/apply` | Atomically apply a persisted evaluation; returns the auditable `practice`/`no_practice` decision |
| `POST` | `/learners/{learner_id}/writing/recommendations/{recommendation_id}/practice` | Resolve an eligible recommendation to one practice or a deterministic `no_practice` outcome |
| `GET` | `/learners/{learner_id}/writing/practices/{practice_id}` | Inspect a persisted Writing practice |
| `POST` | `/learners/{learner_id}/writing/practices/{practice_id}/submit` | Submit an essay only; the server uses the persisted question |
| `GET` | `/learners/{learner_id}/writing/practices/{practice_id}/evaluation` | Read the persisted evaluation for a learner-owned submitted practice |
| `GET` | `/learners/{learner_id}/writing/guidance` | Read provider-free, source-backed guidance for the latest accepted update |
| `GET` | `/knowledge/writing/wiki` | Browse the canonical read-only Writing Task 2 Wiki, or resolve one page with `q` |
| `GET` | `/knowledge/writing/wiki/{page_id}` | Read one canonical Wiki page with breadcrumbs, Knowledge provenance, relations, and neighbors |
| `POST` | `/learners/{learner_id}/writing/agent/turn` | Run one bounded Writing Agent turn |
| `POST` | `/learners/{learner_id}/writing/practices/{practice_id}/complete` | Apply its persisted evaluation and return the next recommendation |

Readiness responses expose only `available` or `unavailable`; connection details
are not returned. See the [Writing API reference](docs/API.md) for request and
response schemas, deterministic scoring, retries, safe error codes, and the
product-score disclaimer. Phase 3 endpoints return the same safe error contract
(`learner_not_found`, `evaluation_not_found`, `evaluation_conflict`,
`learning_source_invalid`).

## Project structure

```text
.
├── app/
│   ├── api/              # thin routes, dependencies, and safe error mapping
│   ├── core/             # typed settings
│   ├── db/               # SQLAlchemy base, engine, and sessions
│   ├── knowledge/        # static official-source snapshot and deterministic retrieval
│   ├── wiki/             # static page registry, relation ledger, validation, and navigation
│   ├── learner/          # frozen policies, evidence extraction, state engine, planner
│   ├── llm/              # provider protocol, DeepSeek adapter, bounded retries
│   ├── models/           # Writing and learning persistence models
│   ├── schemas/          # Pydantic boundary/domain value schemas
│   ├── services/         # evaluation, persistence, learning application, health
│   └── main.py           # app.main:app entry point
├── web/                  # Next.js + TypeScript + Tailwind presentation client
├── migrations/           # reversible Phase 1, Writing, and learning revisions
├── tests/                # unit, API, database, migration, and concurrency tests
├── compose.yaml
├── Dockerfile
├── pyproject.toml
└── docs/
```

Semantic retrieval, generic RAG, and multi-skill workflows remain outside the
implemented system.

## Development guidance

Before changing the project, read these documents in order:

1. [AGENTS.md](AGENTS.md)
2. Current [Phase 11 graph](docs/PHASE11_GRAPH.md) and
   [P11-01 audit](docs/PHASE11_AUDIT.md), frozen
   [Wiki Knowledge policy](docs/WIKI_KNOWLEDGE_POLICY.md), and
   [implementation audit](docs/PHASE11_IMPLEMENTATION_AUDIT.md). P11-02 is
   COMPLETE; External Design Review and Milestone Review are APPROVED; P11-03
   through P11-15 are COMPLETE and P11-16 is INTERNAL_AUDIT_COMPLETE. External
   Implementation Review is CHANGES_REQUESTED.
3. Completed [Phase 10 graph](docs/PHASE10_GRAPH.md), [internal audit](docs/PHASE10_AUDIT.md),
   and [Eval operator workflow](docs/PHASE10_EVAL_OPERATOR.md). Phase 10 is
   complete and merged through PR #14.
4. Completed [Phase 9 graph](docs/PHASE9_GRAPH.md), frozen
   [IELTS Knowledge policy](docs/IELTS_KNOWLEDGE_POLICY.md), and
   [internal audit](docs/PHASE9_AUDIT.md).
5. [Phase 8 graph](docs/PHASE8_GRAPH.md) and frozen
   [Core Learning Agent policy](docs/CORE_LEARNING_AGENT_POLICY.md), with the
   Phase 7 [planner policy](docs/MEMORY_AWARE_PLANNING_POLICY.md) and Phase 6
   [Writing memory policy](docs/WRITING_MEMORY_POLICY.md)
6. [Development loop](docs/DEVELOPMENT_LOOP.md)
7. [Target architecture](docs/ARCHITECTURE.md)

Phase 1 remains complete and preserved in
[docs/PHASE1_GRAPH.md](docs/PHASE1_GRAPH.md). Phase 2 is complete and preserved
in [docs/PHASE2_GRAPH.md](docs/PHASE2_GRAPH.md), with its accepted evidence in
[docs/PHASE2_AUDIT.md](docs/PHASE2_AUDIT.md). Phase 3 is implemented and its
per-node execution record is maintained in
[docs/PHASE3_GRAPH.md](docs/PHASE3_GRAPH.md). Phase 5 is complete and merged
through PR #9.

Phase 6 implements structured hierarchical Writing learning memory (L0 learning
episodes, L1 learning atoms, L2 longitudinal patterns, L3 learner profile) as
read models over the existing PostgreSQL rows — no new tables, no migrations.
Its frozen contract is [docs/WRITING_MEMORY_POLICY.md](docs/WRITING_MEMORY_POLICY.md)
(`writing-memory-v1`, `writing-progress-v1`); execution status is tracked in
[docs/PHASE6_GRAPH.md](docs/PHASE6_GRAPH.md) and the internal audit is
[docs/PHASE6_AUDIT.md](docs/PHASE6_AUDIT.md).

Phase 7 is COMPLETE and merged through PR #11. `writing-practice-gap-memory-v2`
is active for new Writing applies, while historical
`writing-practice-gap-v1` remains supported. Memory is consulted only for exact
maximum-gap ties. The frozen execution record is
[docs/PHASE7_GRAPH.md](docs/PHASE7_GRAPH.md).

Phase 8 is COMPLETE and merged through PR #12. Its bounded,
Writing-only Core Learning Agent v1 remains available through
`POST /learners/{learner_id}/writing/agent/turn`; granular APIs remain
supported. Phase 9 is COMPLETE and merged through PR #13 (merge commit
`75a667ff4ce16b79e7d4ba517081e1bd3d96fd57`); both external reviews are
approved. The completed execution record and audit are
[docs/PHASE9_GRAPH.md](docs/PHASE9_GRAPH.md) and
[docs/PHASE9_AUDIT.md](docs/PHASE9_AUDIT.md). Phase 10 is COMPLETE and merged
through PR #14 (merge commit
`c7a5f991df9c556408295d01194f1f17c13653b5`). Phase 11 P11-00 and P11-01 are
COMPLETE; Graph Review is APPROVED, External Audit Review is APPROVED, and
P11-02 is COMPLETE. Phase 11 External Design Review is APPROVED, and P11-03
through P11-15 are COMPLETE. Phase 11 Milestone Review is APPROVED, and P11-16
is INTERNAL_AUDIT_COMPLETE. External Implementation Review is
CHANGES_REQUESTED, and Phase 11 is NOT COMPLETE.

## Phase 5 Web MVP

Phase 5 is complete and merged through PR #9. The Chinese-first Next.js, TypeScript, and Tailwind frontend is a presentation client for FastAPI and PostgreSQL; it does not own scoring, learner state, planning, or practice policy.
