# IELTS Learning Agent

IELTS Learning Agent is the foundation of a long-term adaptive IELTS learning
system. The target product will maintain structured learner state, evaluate
learning outcomes, retain useful learning history, and select future practice;
it is not intended to be only a chatbot or a thin LLM wrapper.

## Current status

**Phase 1 — Foundation is complete.** The repository provides:

- an importable FastAPI application on Python 3.12+;
- typed Pydantic v2 settings with secret-safe database configuration;
- PostgreSQL, SQLAlchemy 2.x session/base infrastructure, and Alembic;
- an empty reversible baseline migration at `0001_phase1`;
- validated IELTS band and health response schemas;
- `/health/live` and `/health/ready` APIs;
- 29 pytest tests, including PostgreSQL integration coverage;
- runtime/test Docker image targets and an integrated Compose stack with
  isolated development and test databases.

**Phase 2 — Writing Evaluation Pipeline is planned and starting.** Its authorized
dependency graph is documented in [docs/PHASE2_GRAPH.md](docs/PHASE2_GRAPH.md),
but no Phase 2 runtime functionality has been implemented yet. There is no LLM
integration, Writing Evaluator, learner-state logic, planner, learning-memory
logic, agent runtime, RAG, or IELTS practice workflow in the application.

## Technology stack

| Area | Implemented foundation |
| --- | --- |
| Backend | Python 3.12+, FastAPI, Pydantic v2 |
| Persistence | PostgreSQL, SQLAlchemy 2.x, Alembic |
| Testing | pytest, httpx |
| Infrastructure | Docker, Docker Compose |

The planned Next.js frontend and learner-state or multi-skill practice
functionality are outside Phase 2.

## Quick start with Docker

Requirements: Docker Desktop or Docker Engine with Docker Compose.

1. Copy `.env.example` to `.env`.
2. Replace every placeholder password in `.env`; do not commit that file.
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

Readiness responses expose only `available` or `unavailable`; connection details
are not returned.

## Project structure

```text
.
├── app/
│   ├── api/routes/       # thin HTTP routes
│   ├── core/             # typed settings
│   ├── db/               # SQLAlchemy base, engine, and sessions
│   ├── schemas/          # Pydantic boundary/domain value schemas
│   ├── services/         # deterministic health service
│   └── main.py           # app.main:app entry point
├── migrations/           # Alembic environment and baseline revision
├── tests/                # unit, API, database, and migration tests
├── compose.yaml
├── Dockerfile
├── pyproject.toml
└── docs/
```

No speculative agent, evaluator, memory, planner, LLM, or IELTS skill packages
are present.

## Development guidance

Before changing the project, read these documents in order:

1. [AGENTS.md](AGENTS.md)
2. [Phase 2 graph](docs/PHASE2_GRAPH.md)
3. [Development loop](docs/DEVELOPMENT_LOOP.md)
4. [Target architecture](docs/ARCHITECTURE.md)

Phase 1 remains complete and preserved in
[docs/PHASE1_GRAPH.md](docs/PHASE1_GRAPH.md). Phase 2 implementation must follow
the Phase 2 graph node by node; this planning transition does not itself
implement or validate any Phase 2 runtime capability.
