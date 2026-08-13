# IELTS Learning Agent

IELTS Learning Agent is the foundation of a long-term adaptive IELTS learning
system. The target product will maintain structured learner state, evaluate
learning outcomes, retain useful learning history, and select future practice;
it is not intended to be only a chatbot or a thin LLM wrapper.

## Current status

**Phase 1 — Foundation and Phase 2 — Writing Evaluation Pipeline are complete.**
Phase 3 — Learner State & Adaptive Planning is planned and its graph is
authorized, but no Phase 3 runtime node has been executed. The repository
currently provides:

- a FastAPI application with liveness, readiness, and Writing Task 2 evaluation;
- strict Pydantic v2 request, provider-result, response, and error boundaries;
- pre-provider input ceilings of 2,000 question characters and 20,000 essay
  characters, while essays below 250 words remain valid;
- deterministic word counting and product-band aggregation;
- a vendor-independent provider protocol and environment-configured DeepSeek
  HTTP adapter;
- a versioned `writing-task2-v1` rubric contract and application-owned provider,
  model, prompt, rubric, scoring-policy, and thinking-mode metadata;
- bounded provider retries with increasing backoff and safe API failure mapping;
- atomic Writing attempt/evaluation persistence in PostgreSQL through SQLAlchemy
  2.x and the reversible `0002_writing` Alembic migration;
- deterministic FakeProvider tests with no live provider or credential
  requirement;
- runtime/test Docker targets and isolated development/test Compose databases.

The completed Phase 2 dependency graph is preserved in
[docs/PHASE2_GRAPH.md](docs/PHASE2_GRAPH.md). The planned Phase 3 scope and
dependency order are documented in [docs/PHASE3_GRAPH.md](docs/PHASE3_GRAPH.md).
Learner state and planning are not implemented yet, and learning memory, an
agent runtime, RAG, frontend behavior, and Speaking, Reading, and Listening
workflows remain outside the implemented system.

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
2. [Phase 3 graph](docs/PHASE3_GRAPH.md)
3. [Development loop](docs/DEVELOPMENT_LOOP.md)
4. [Target architecture](docs/ARCHITECTURE.md)

Phase 1 remains complete and preserved in
[docs/PHASE1_GRAPH.md](docs/PHASE1_GRAPH.md). Phase 2 is complete and preserved
in [docs/PHASE2_GRAPH.md](docs/PHASE2_GRAPH.md), with its accepted evidence in
the final audit. The Phase 3 graph defines planned scope only: `P3-01` is
`READY`, but execution still requires separate explicit authorization.

The completed validation evidence is recorded in the
[Phase 2 final audit](docs/PHASE2_AUDIT.md).
