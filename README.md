# IELTS Learning Agent

IELTS Learning Agent is the foundation of a long-term adaptive IELTS learning
system. The target product will maintain structured learner state, evaluate
learning outcomes, retain useful learning history, and select future practice;
it is not intended to be only a chatbot or a thin LLM wrapper.

## Current status

**Phase 1 — Foundation, Phase 2 — Writing Evaluation Pipeline, Phase 3 —
Learner State & Adaptive Planning, and Phase 4 — Adaptive Writing Practice are
implemented on this branch pending external review.** Phase 4 closes the
bounded Writing loop: a persisted Phase 3 recommendation may resolve to one
targeted Task 2 practice; the learner submits an essay against the persisted
authoritative question; the existing evaluator persists one attempt/evaluation;
and Phase 3 applies that evaluation to return the next recommendation. The
generate, inspect, submit, and complete actions stay separate. `no_practice`
never calls a generator, and Phase 5 is implemented on `phase/5-web-product-mvp` and FINAL_REVIEW_PENDING. Phase 6 is NOT_STARTED.

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
Learning memory, an agent runtime, RAG, automatic lesson or
exercise generation, and Speaking, Reading, and Listening workflows remain
outside the implemented system (future phases).

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

Learning memory, an agent runtime, RAG, automatic content generation, a
frontend, and multi-skill workflows remain outside the implemented system.

## Development guidance

Before changing the project, read these documents in order:

1. [AGENTS.md](AGENTS.md)
2. [Phase 4 graph](docs/PHASE4_GRAPH.md)
3. [Development loop](docs/DEVELOPMENT_LOOP.md)
4. [Target architecture](docs/ARCHITECTURE.md)

Phase 1 remains complete and preserved in
[docs/PHASE1_GRAPH.md](docs/PHASE1_GRAPH.md). Phase 2 is complete and preserved
in [docs/PHASE2_GRAPH.md](docs/PHASE2_GRAPH.md), with its accepted evidence in
the final audit. Phase 3 is implemented and its per-node execution record is
maintained in [docs/PHASE3_GRAPH.md](docs/PHASE3_GRAPH.md).

The completed validation evidence is recorded in the
[Phase 2 final audit](docs/PHASE2_AUDIT.md).

## Phase 5 Web MVP

Phase 5 is implemented and awaits final external review. The Chinese-first Next.js, TypeScript, and Tailwind frontend is a presentation client for FastAPI and PostgreSQL; it does not own scoring, learner state, planning, or practice policy.