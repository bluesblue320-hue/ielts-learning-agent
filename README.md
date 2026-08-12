# IELTS Learning Agent

IELTS Learning Agent is intended to become a long-term adaptive IELTS learning system. The target product will maintain structured learner state, evaluate learning outcomes, retain useful learning history, and choose appropriate future practice. It is not intended to be only a chatbot or a thin LLM wrapper.

## Current status

The project is in **Phase 1 — Foundation**, but Phase 1 implementation has not started. The repository currently contains project guidance and architecture documentation only; no API, database, learning agent, evaluator, planner, memory logic, or IELTS practice module is implemented yet.

Phase 1 is limited to establishing:

- a FastAPI backend foundation;
- PostgreSQL connectivity;
- SQLAlchemy 2.x and Alembic infrastructure;
- Pydantic v2 schemas;
- health APIs and automated tests;
- Docker and Docker Compose support;
- accurate project documentation.

Later phases may add a writing-first learning loop and other IELTS capabilities, but those are target designs rather than current features.

## Planned technology stack

| Area | Planned technology |
| --- | --- |
| Frontend | Next.js, TypeScript, Tailwind CSS |
| Backend | Python 3.12+, FastAPI, Pydantic v2 |
| Persistence | PostgreSQL, SQLAlchemy 2.x, Alembic |
| Testing | pytest, httpx |
| Infrastructure | Docker, Docker Compose |

The frontend is part of the longer-term stack and is not a required Phase 1 deliverable unless the phase graph is explicitly revised.

## Project structure

The repository currently has a documentation-only structure:

```text
.
├── AGENTS.md
├── ARCHITECTURE.md          # compatibility pointer
├── README.md
└── docs/
    ├── ARCHITECTURE.md      # canonical target architecture
    ├── DEVELOPMENT_LOOP.md  # how to execute one graph node
    └── PHASE1_GRAPH.md      # Phase 1 scope and dependency graph
```

Application directories will be introduced only when their graph node is selected. The long-term backend may use focused packages such as `api`, `core`, `db`, `models`, `schemas`, and `services`; directories for future agent capabilities must not be created speculatively.

## Development guidance

Before making implementation changes, read these documents in order:

1. [AGENTS.md](AGENTS.md)
2. [Phase 1 graph](docs/PHASE1_GRAPH.md)
3. [Development loop](docs/DEVELOPMENT_LOOP.md)
4. [Target architecture](docs/ARCHITECTURE.md), when architectural context is relevant

The graph defines what may be built in Phase 1. The development loop defines how to execute and validate the selected node. Phase 1 execution must begin only after explicit instruction.
