# IELTS Learning Agent

IELTS Learning Agent is the foundation of a long-term adaptive IELTS learning
system. The target product will maintain structured learner state, evaluate
learning outcomes, retain useful learning history, and select future practice;
it is not intended to be only a chatbot or a thin LLM wrapper.

## Current status

**Phase 1 — Foundation is complete. Phase 2 — Writing Evaluation Pipeline is
implemented.** The repository provides:

- a FastAPI application with liveness, readiness, and Writing Task 2 evaluation;
- strict Pydantic v2 request, provider-result, response, and error boundaries;
- deterministic word counting and product-band aggregation;
- a vendor-independent provider protocol and environment-configured DeepSeek
  HTTP adapter;
- bounded provider retries and safe API failure mapping;
- atomic Writing attempt/evaluation persistence in PostgreSQL through SQLAlchemy
  2.x and the reversible `0002_writing` Alembic migration;
- deterministic FakeProvider tests with no live provider or credential
  requirement;
- runtime/test Docker targets and isolated development/test Compose databases.

The authorized dependency graph is documented in
[docs/PHASE2_GRAPH.md](docs/PHASE2_GRAPH.md). Phase 2 does not implement learner
state, planning, learning memory, an agent runtime, RAG, frontend behavior, or
Speaking, Reading, and Listening workflows.

## Technology stack

| Area | Implemented Phase 2 stack |
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

Readiness responses expose only `available` or `unavailable`; connection details
are not returned. See the [Writing API reference](docs/API.md) for request and
response schemas, deterministic scoring, retries, safe error codes, and the
product-score disclaimer.

## Project structure

```text
.
├── app/
│   ├── api/              # thin routes, dependencies, and safe error mapping
│   ├── core/             # typed settings
│   ├── db/               # SQLAlchemy base, engine, and sessions
│   ├── llm/              # provider protocol, DeepSeek adapter, bounded retries
│   ├── models/           # Writing persistence models
│   ├── schemas/          # Pydantic boundary/domain value schemas
│   ├── services/         # evaluation, persistence, and health services
│   └── main.py           # app.main:app entry point
├── migrations/           # reversible Phase 1 and Writing revisions
├── tests/                # unit, API, database, and migration tests
├── compose.yaml
├── Dockerfile
├── pyproject.toml
└── docs/
```

No learner-state, memory, planner, agent runtime, RAG, frontend, or multi-skill
practice implementation is present.

## Development guidance

Before changing the project, read these documents in order:

1. [AGENTS.md](AGENTS.md)
2. [Phase 2 graph](docs/PHASE2_GRAPH.md)
3. [Development loop](docs/DEVELOPMENT_LOOP.md)
4. [Target architecture](docs/ARCHITECTURE.md)

Phase 1 remains complete and preserved in
[docs/PHASE1_GRAPH.md](docs/PHASE1_GRAPH.md). Phase 2 implementation and its
final audit follow the Phase 2 graph node by node. A later phase still requires
separate authorization and its own graph.

The completed validation evidence is recorded in the
[Phase 2 final audit](docs/PHASE2_AUDIT.md).
