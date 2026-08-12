# IELTS Learning Agent Architecture

## Document status

This document describes the **long-term target architecture** and the intended writing-first MVP. It is not an implementation report. At present, the repository contains guidance documents only; none of the runtime components below has been implemented.

Phase 1 is strictly a foundation phase. Its allowed deliverables are defined by [PHASE1_GRAPH.md](PHASE1_GRAPH.md). Later-phase components described here must not be implemented during Phase 1 without an explicit scope change.

## Architecture goal

The target system closes an adaptive learning loop:

```text
Goal
  -> Observe learner state
  -> Plan
  -> Practice
  -> Evaluate
  -> Update learner state
  -> Store learning memory
  -> Replan
```

The design favors one coordinating learning agent plus deterministic services and specialized tools. It should remain simple, testable, and vendor-independent as it grows.

## Target components

```text
Client
  |
  v
FastAPI API layer
  |
  v
One core IELTS Learning Agent
  |-- Learner Model
  |-- Planner
  |-- Memory
  |-- Evaluator
  `-- Tool Layer
      |-- Writing
      |-- Speaking       (future)
      |-- Reading        (future)
      `-- Listening      (future)
  |
  +-- Deterministic services
  +-- PostgreSQL persistence
  `-- LLM provider abstraction (future)
```

The core agent coordinates the learning loop. Planner, Memory, Evaluator, and IELTS tools are responsibilities within that system, not separate agents by default.

| Component | Target responsibility | Phase 1 status |
| --- | --- | --- |
| Core Learning Agent | Coordinate state, planning, tools, evaluation, and replanning | Deferred |
| Learner Model | Represent goals, current level, skill mastery, weaknesses, and history as structured persistent data | Schemas may be defined; behavior is deferred |
| Planner | Select the next learning objective using deterministic priorities, with constrained generation where useful | Deferred |
| Memory | Separate stable profile data, learning events, and derived patterns | Storage logic and retrieval are deferred |
| Evaluator | Convert learning outcomes into validated structured evidence | Deferred |
| Tool Layer | Expose focused learning activities behind explicit interfaces | Deferred |
| API Layer | Validate HTTP boundaries and call application services | Foundation only |
| Persistence | Store durable application data in PostgreSQL through SQLAlchemy and Alembic | Infrastructure only |

## Responsibility boundaries

- API routes remain thin: HTTP validation and transport belong in the API layer; business behavior belongs in services or domain modules.
- Learner state is structured and persisted; prompts and conversation history are not sources of truth.
- State describes the learner now. Memory describes prior events or patterns. They remain separate concepts.
- Deterministic rules decide what can be calculated reliably. LLMs may assist with generation or qualitative evaluation only through validated structured outputs.
- Database schema changes use Alembic migrations with upgrade and downgrade paths when reasonably possible.
- New modules and dependencies are introduced only when a selected graph node requires them.

## Writing-first MVP target

Writing is the intended first learning domain after the foundation is complete. The target flow is:

```text
Writing goal
  -> Writing task
  -> Learner submission
  -> Structured writing evaluation
  -> Validated evidence
  -> Learner-state update
  -> Learning-memory event
  -> Next-task planning
```

This is a later-phase target. Phase 1 must not implement the writing evaluator, LLM provider integration, learner-state update logic, learning-memory logic, planner, or task generation.

## Phase 1 architecture boundary

Phase 1 may establish only the supporting foundation:

```text
FastAPI application shell
  + Pydantic boundary schemas
  + PostgreSQL configuration
  + SQLAlchemy session/base infrastructure
  + Alembic migration infrastructure
  + liveness/readiness APIs
  + automated tests
  + Docker/Docker Compose
```

Explicitly deferred capabilities include DeepSeek or other LLM integrations, Writing Evaluator, Planner, Learning Memory behavior, RAG, Redis, LangGraph, multi-agent orchestration, and Speaking, Reading, or Listening modules.

## Evolution rule

Architecture follows verified product requirements. Complete the current phase graph, report its acceptance evidence, and stop. A later phase starts only with explicit instruction. Node-level execution follows [DEVELOPMENT_LOOP.md](DEVELOPMENT_LOOP.md).
