# IELTS Learning Agent

IELTS Learning Agent is the foundation of a long-term adaptive IELTS learning
system. The target product will maintain structured learner state, evaluate
learning outcomes, retain useful learning history, and select future practice;
it is not intended to be only a chatbot or a thin LLM wrapper.

## Current status

**Phase 1 — Foundation is complete.** The repository now provides:

- an importable FastAPI application on Python 3.12+;
- typed Pydantic v2 settings with secret-safe database configuration;
- PostgreSQL, SQLAlchemy 2.x session/base infrastructure, and Alembic;
- an empty reversible baseline migration at `0001_phase1`;
- validated IELTS band and health response schemas;
- `/health/live` and `/health/ready` APIs;
- 29 pytest tests, including PostgreSQL integration coverage;
- runtime/test Docker image targets and an integrated Compose stack.

Phase 2 has not started. No LLM integration, evaluator, planner, learning-memory
logic, agent runtime, RAG, or IELTS practice workflow is implemented.

## Technology stack

| Area | Implemented foundation |
| --- | --- |
| Backend | Python 3.12+, FastAPI, Pydantic v2 |
| Persistence | PostgreSQL, SQLAlchemy 2.x, Alembic |
| Testing | pytest, httpx |
| Infrastructure | Docker, Docker Compose |

The planned Next.js frontend and all learner-facing practice functionality are
outside Phase 1.

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
2. [Phase 1 graph](docs/PHASE1_GRAPH.md)
3. [Development loop](docs/DEVELOPMENT_LOOP.md)
4. [Target architecture](docs/ARCHITECTURE.md)

Phase 1 is stopped at `P1-11`. Starting the next phase requires explicit
authorization and an updated phase graph.
