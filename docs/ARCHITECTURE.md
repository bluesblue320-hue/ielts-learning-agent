# IELTS Learning Agent Architecture

## Document status

This document distinguishes the **implemented architecture** from the
long-term adaptive-learning target. Phase 1 foundation is implemented: FastAPI,
typed configuration, PostgreSQL/SQLAlchemy/Alembic infrastructure, foundation
schemas, health APIs, tests, and Docker integration. Phase 2 adds the Writing
Task 2 evaluation API, a vendor-independent provider boundary with a DeepSeek
adapter, validated structured output, deterministic product-band aggregation,
atomic PostgreSQL persistence, bounded failure handling, and deterministic
local, CI, and Docker validation. Phase 3 adds the deterministic learner-state
path: learner creation and four-skill materialized state, canonical evidence
extraction, an exact-Decimal EWMA replay engine, a target-gap practice planner,
an atomic idempotent learning-application service, learner/learning REST APIs,
and database-safe concurrency hardening. Phase 4 closes the bounded adaptive
Writing loop with decision-gated practice generation, durable practice
ownership, a submission claim protocol, atomic reuse of Phase 2 persistence,
and Phase 3 completion/replanning. Phase 5 implements the Chinese-first Next.js presentation layer, typed HTTP client, browser presentation cache, real Chromium E2E, and CI gate. Generation, submission, and completion are
separate product actions; no automatic next-practice generation occurs. Phase 6 implements the hierarchical Learning Memory subsystem (L0-L3) as deterministic read models over the existing durable Writing history, with four frozen read APIs (`history`, `history/{episode_id}`, `progress`, `context`), `/history` and `/progress` web UX, and server-authoritative dashboard resume; no new table, migration, or external memory runtime was introduced. The
learning-loop components below remain target designs unless their status says
otherwise.

The completed [PHASE1_GRAPH.md](PHASE1_GRAPH.md) remains the historical Phase 1
execution record, and [PHASE2_GRAPH.md](PHASE2_GRAPH.md) records the completed
Phase 2 implementation. [PHASE3_GRAPH.md](PHASE3_GRAPH.md) is the executed
Phase 3 execution record with per-node status.

## Phase 3 components (implemented)

```text
Client
  |
  +--> FastAPI Learner/Learning API (implemented)
  |      -> POST /learners
  |      -> GET  /learners/{id}/state
  |      -> POST /learners/{id}/writing/evaluations/{evaluation_id}/apply
  |
  +--> app/learner/ (deterministic domain components)
  |      -> writing_policy.py    frozen taxonomy/state-policy constants (P3-02)
  |      -> planning_policy.py   frozen planner constants (P3-08)
  |      -> writing_evidence.py  canonical 4-skill evidence extraction (P3-06)
  |      -> state_engine.py      EWMA replay/rebuild, quantization (P3-07)
  |      -> planner.py           target-gap practice planner (P3-09)
  |
  +--> app/services/learning_application.py (P3-10)
  |      -> atomic transaction: 1 update + 4 evidence + 4 states + 1 decision
  |      -> idempotent replay, cross-owner conflict, per-learner row lock
  |
  `--> app/models/learning.py + migration 0003_learning (P3-04/P3-05)
         -> learners, learning_updates, learning_evidence,
            learner_skill_states, practice_recommendations
```

All learner-state computation is deterministic and provider-free: no LLM is
used for state updates or planning. Planner policy and decision contracts are
frozen in docs/WRITING_STATE_POLICY.md and docs/PRACTICE_PLANNING_POLICY.md.

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
| Learner Model | Represent goals, current level, skill mastery, weaknesses, and history as structured persistent data | Implemented Phase 3 learner state and persistence |
| Planner | Select the next learning objective using deterministic priorities, with constrained generation where useful | Implemented deterministic Phase 3 planner |
| Memory | Separate stable profile data, learning events, and derived patterns | Implemented Phase 6 read models (`writing-memory-v1` / `writing-progress-v1`); no new tables |
| Writing Evaluator | Convert a Task 2 submission into validated structured evidence through the provider protocol | Implemented for Writing Task 2 only |
| LLM Provider | Isolate vendor HTTP behavior behind a typed contract | Protocol, test fake, and DeepSeek adapter implemented; no runtime fake selection |
| Tool Layer | Expose focused learning activities behind explicit interfaces | Wider practice tools deferred |
| API Layer | FastAPI is application/domain authority; Next.js is presentation only | Implemented through Phase 5 |
| Persistence | Store durable application data in PostgreSQL through SQLAlchemy and Alembic | PostgreSQL is source of truth for Writing, learner state, recommendations, and practices |

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
rate-limit, or transient failures, with bounded 0.25-second then 0.5-second
backoff. Account/billing failures are not retried and map to a safe 503 response.
DeepSeek thinking mode is a strict environment-backed enabled/disabled setting,
is sent explicitly on every request, and is persisted as application-owned
metadata. Deterministic FakeProvider tests verify the
application trust boundary, request construction, structured-output validation,
and safe handling of untrusted content; they do not prove real-model immunity to
prompt injection, and perfect prevention is not claimed. The computed product
band is a documented application policy, not a claim of exact equivalence to an
official final IELTS Writing band. See [API.md](API.md) for the public contract.

Phase 3 implements learner-state updates and deterministic planning. Phase 4
implements Writing practice generation and the bounded adaptive Writing closed
loop. Phase 5 implements the Next.js presentation layer. Long-term semantic
memory, RAG, Reading, Listening, Speaking, and the wider multi-skill Learning
Agent remain future targets.
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
During Phase 1, planner, learner state, Learning Memory behavior, RAG, Redis,
LangGraph, multi-agent orchestration, and Speaking, Reading, or Listening were
deferred. Phase 3 later implemented learner state and planning; Phase 4 later
implemented the bounded adaptive Writing loop. Long-term memory, RAG, and the
remaining skills remain future work.

## Evolution rule

Architecture follows verified product requirements. Phase 1 is complete and
stopped at `P1-11`; Phase 2 is complete and stopped at `P2-15`; Phase 3 is
complete; Phase 4 is the accepted implementation baseline; Phase 5 is
implemented and merged; Phase 6 is COMPLETE and merged to `master` through PR
#10 (merge commit `b8e419d8c146c921539f4654b5aeb0b56ed6f425`): hierarchical
Learning Memory read models over the existing Writing history, four frozen
read APIs, `/history` and `/progress` UX, and dashboard resume; no new table,
no migration, no provider abstraction. External Review is APPROVED. Phase 7
remains NOT_STARTED.
Node-level execution follows [DEVELOPMENT_LOOP.md](DEVELOPMENT_LOOP.md).

## Phase 5 presentation layer

`web/` is a Chinese-first Next.js presentation layer. It calls FastAPI over JSON, caches only learner navigation/recommendation presentation fields in browser storage, and leaves evaluation, learner state, planning, lifecycle validation, and persistence authoritative in FastAPI/PostgreSQL.
## Phase 5 status

Next.js presentation, FastAPI application/domain authority, and PostgreSQL source of truth are implemented. Phase 6 is COMPLETE and merged to `master` through PR #10: the hierarchical learning memory subsystem (L0-L3 read models, history/progress/context APIs, `/history` and `/progress` UX, dashboard resume) is implemented, internally audited, externally approved, and merged. RAG, wider multi-skill work, and Phase 7 remain future and are NOT_STARTED.
