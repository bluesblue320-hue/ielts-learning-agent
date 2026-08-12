# IELTS Learning Agent Architecture

## Document status

This document distinguishes the **implemented Phase 2 architecture** from the
long-term adaptive-learning target. Phase 1 foundation is implemented: FastAPI,
typed configuration, PostgreSQL/SQLAlchemy/Alembic infrastructure, foundation
schemas, health APIs, tests, and Docker integration. Phase 2 adds the Writing
Task 2 evaluation API, a vendor-independent provider boundary with a DeepSeek
adapter, validated structured output, deterministic product-band aggregation,
atomic PostgreSQL persistence, bounded failure handling, and deterministic
local, CI, and Docker validation. The learning-loop components below remain
target designs unless their status says otherwise.

The completed [PHASE1_GRAPH.md](PHASE1_GRAPH.md) remains the historical Phase 1
execution record. Current work is bounded by the authorized Phase 2 graph;
components outside it require a later explicit phase authorization.

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
  +--> FastAPI Writing API (implemented)
  |      -> Writing Evaluation Service
  |      -> LLM Provider protocol
  |           `-> DeepSeek adapter
  |      -> Pydantic structured-output validation
  |      -> Deterministic product-band aggregation
  |      -> Atomic SQLAlchemy/PostgreSQL persistence
  |
  `--> One core IELTS Learning Agent (future phase)
         |-- Learner Model
         |-- Planner
         |-- Memory
         |-- Evaluator
         `-- Tool Layer
             |-- Writing practice
             |-- Speaking
             |-- Reading
             `-- Listening
```

The core agent coordinates the learning loop. Planner, Memory, Evaluator, and IELTS tools are responsibilities within that system, not separate agents by default.

| Component | Responsibility | Current status |
| --- | --- | --- |
| Core Learning Agent | Coordinate state, planning, tools, evaluation, and replanning | Deferred |
| Learner Model | Represent goals, current level, skill mastery, weaknesses, and history as structured persistent data | IELTS band value schema only; learner state and persistence are deferred |
| Planner | Select the next learning objective using deterministic priorities, with constrained generation where useful | Deferred |
| Memory | Separate stable profile data, learning events, and derived patterns | Storage logic and retrieval are deferred |
| Writing Evaluator | Convert a Task 2 submission into validated structured evidence through the provider protocol | Implemented for Writing Task 2 only |
| LLM Provider | Isolate vendor HTTP behavior behind a typed contract | Protocol, test fake, and DeepSeek adapter implemented; no runtime fake selection |
| Tool Layer | Expose focused learning activities behind explicit interfaces | Wider practice tools deferred |
| API Layer | Validate HTTP boundaries and call application services | Health APIs and `POST /writing/evaluate` implemented |
| Persistence | Store durable application data in PostgreSQL through SQLAlchemy and Alembic | Writing attempts and evaluations implemented through `0002_writing`; learner data deferred |

## Responsibility boundaries

- API routes remain thin: HTTP validation and transport belong in the API layer; business behavior belongs in services or domain modules.
- Learner state is structured and persisted; prompts and conversation history are not sources of truth.
- State describes the learner now. Memory describes prior events or patterns. They remain separate concepts.
- Deterministic rules decide what can be calculated reliably. LLMs may assist with generation or qualitative evaluation only through validated structured outputs.
- Database schema changes use Alembic migrations with upgrade and downgrade paths when reasonably possible.
- New modules and dependencies are introduced only when a selected graph node requires them.

## Writing-first MVP target

Phase 2 implements this bounded Writing evaluation flow:

```text
Task 2 question + essay (untrusted input)
  -> strict request validation + deterministic word count
  -> versioned evaluator request with trusted rubric/output contract
  -> provider protocol / DeepSeek adapter
  -> Pydantic validation of structured provider output
  -> deterministic equal-weight product-band aggregation
  -> atomic attempt + evaluation transaction
  -> explicit API response or safe normalized failure
```

Provider calls have at most three attempts and retry only normalized timeout,
rate-limit, or transient failures. Deterministic FakeProvider tests verify the
application trust boundary, request construction, structured-output validation,
and safe handling of untrusted content; they do not prove real-model immunity to
prompt injection, and perfect prevention is not claimed. The computed product
band is a documented application policy, not a claim of exact equivalence to an
official final IELTS Writing band. See [API.md](API.md) for the public contract.

Learner-state updates, learning memory, planning, task generation, and the wider

closed loop remain later-phase targets.
## Phase 1 architecture boundary

Phase 1 established the following supporting foundation:

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

DeepSeek integration and the Writing Evaluator were explicitly deferred during
Phase 1 and were later implemented only within the authorized Phase 2 boundary.
Planner, learner state, Learning Memory behavior, RAG, Redis, LangGraph,
multi-agent orchestration, and Speaking, Reading, or Listening remain deferred.

## Evolution rule

Architecture follows verified product requirements. Phase 1 is complete and
stopped at `P1-11`; Phase 2 implementation follows its authorized graph and stops
at `P2-15`. Every phase requires explicit execution authority, and Phase 3 or any
other subsequent phase requires separate authorization and its own graph.
Node-level execution follows [DEVELOPMENT_LOOP.md](DEVELOPMENT_LOOP.md).
