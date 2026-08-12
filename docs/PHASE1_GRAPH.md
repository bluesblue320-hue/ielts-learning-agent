# Phase 1 Development Graph

## Purpose and authority

This document defines **what** may be implemented in Phase 1 and the order imposed by dependencies. [DEVELOPMENT_LOOP.md](DEVELOPMENT_LOOP.md) defines **how** to execute each selected node.

Creating this graph does not start Phase 1. Current execution status is **not started**. Do not select or implement the first node until explicitly instructed.

## Scope boundary

Phase 1 is limited to FastAPI foundation, PostgreSQL, SQLAlchemy 2.x, Alembic, Pydantic v2 schemas, health APIs, tests, Docker, Docker Compose, and documentation.

The following are outside Phase 1: DeepSeek or other LLM integrations, Writing Evaluator, Planner, Learning Memory logic, RAG, Redis, LangChain, LangGraph, multi-agent architecture, and Writing, Speaking, Reading, or Listening learning workflows. Schemas may describe stable foundation data only when a node explicitly requires them; they must not embed deferred behavior.

## Node states

Each node has one state:

```text
NOT_STARTED -> READY -> ACTIVE -> VERIFYING -> COMPLETE
                         |          |
                         v          v
                       FIXING <-----+

Any state -> BLOCKED when required input or authority is unavailable.
```

A node is `READY` only when all dependencies are `COMPLETE`. Only one node should be `ACTIVE` at a time. A failed validation routes the same node to `FIXING`; it never unlocks downstream work.

## Dependency graph

```text
P1-01 -> P1-02 FastAPI shell
P1-01 -> P1-03 Configuration
P1-03 -> P1-04 PostgreSQL development service
P1-03 + P1-04 -> P1-05 SQLAlchemy foundation
P1-05 -> P1-06 Alembic
P1-02 + P1-03 -> P1-07 Foundation Pydantic schemas
P1-02 + P1-05 + P1-07 -> P1-08 Health APIs
P1-06 + P1-08 -> P1-09 Automated validation suite
P1-09 -> P1-10 Docker application integration
P1-10 -> P1-11 Documentation and Phase 1 acceptance
P1-11 -> STOP
```

The diagram shows the normal path. The dependency table below is authoritative.

## Nodes and acceptance gates

| Node | Deliverable | Dependencies | Required validation | Acceptance condition |
| --- | --- | --- | --- | --- |
| `P1-01` | Minimal repository and backend scaffold, dependency metadata, `.gitignore`, and `.env.example` | None | Inspect tree and dependency metadata; verify no secret or speculative module is added | Structure supports the remaining Phase 1 nodes and contains no application feature logic |
| `P1-02` | Importable FastAPI application shell with explicit startup entry point | `P1-01` | Import app; start it in a test context; run targeted tests | App imports and starts without external service calls or IELTS behavior |
| `P1-03` | Typed environment-based configuration using Pydantic v2 patterns | `P1-01` | Test defaults, required values, invalid values, and secret-safe examples | Configuration is validated, environment-specific, and contains no committed credentials |
| `P1-04` | Isolated PostgreSQL development/test service with secret-safe Docker Compose configuration | `P1-03` | Validate Compose configuration; start PostgreSQL; confirm health and connectivity; stop cleanly | A documented local PostgreSQL service is reproducible without committed credentials or application images |
| `P1-05` | SQLAlchemy 2.x engine, session, and declarative base infrastructure | `P1-03`, `P1-04` | Import database modules; exercise connection/session behavior against the isolated PostgreSQL service | SQLAlchemy uses 2.x APIs and database failures are explicit and testable |
| `P1-06` | Alembic configuration and a valid baseline migration path | `P1-05` | Check current heads; run upgrade, downgrade, and re-upgrade against an isolated database | Migration state is reproducible and reversible where reasonably possible |
| `P1-07` | Foundation Pydantic schemas and meaningful domain validation needed by Phase 1 | `P1-02`, `P1-03` | Unit-test valid and invalid inputs, including IELTS band range and half-band increments when present | Schemas are typed, use Pydantic v2, avoid mutable defaults, and contain no evaluation/planning logic |
| `P1-08` | Liveness and database-readiness health APIs with explicit response schemas | `P1-02`, `P1-05`, `P1-07` | Test success and dependency-failure responses with `httpx`; verify routes remain thin | Liveness does not require the database; readiness reports database availability without leaking internals |
| `P1-09` | Consolidated automated test suite for all completed foundation behavior | `P1-06`, `P1-08` | Run targeted tests and the relevant full `pytest` suite from a clean environment | Tests are deterministic, failures are visible, and every completed node has useful coverage |
| `P1-10` | Docker image and integrated Docker Compose environment for API plus PostgreSQL | `P1-09` | Validate Compose configuration; build; start; check health; run migrations/tests; stop cleanly | A documented clean checkout workflow brings up healthy services without embedded secrets |
| `P1-11` | Documentation synchronized with the verified implementation and final Phase 1 evidence | `P1-10` | Re-run full tests, migration checks, Docker checks, link checks, and inspect repository diff | All Phase 1 acceptance criteria are evidenced and documentation makes no unsupported claims |

## Transitions

1. Select the lowest-risk `READY` node whose dependencies are complete.
2. Execute the node using [DEVELOPMENT_LOOP.md](DEVELOPMENT_LOOP.md).
3. Move `ACTIVE -> VERIFYING` only after the planned change is implemented.
4. Move `VERIFYING -> COMPLETE` only when every node validation and acceptance condition passes and the logical change is reviewed and committed.
5. Recompute readiness after completion. Direct dependants become `READY` only when all their dependencies are complete.
6. Do not combine nodes merely because they touch nearby files. If a dependency proves incorrect, update this graph explicitly before continuing.

## Failure routing

When implementation, tests, migrations, imports, database checks, or Docker validation fail:

```text
current node
  -> capture reproducible failure
  -> FIXING
  -> identify root cause
  -> apply the smallest in-scope correction
  -> rerun targeted validation
  -> rerun the node's relevant validation set
  -> review
  -> COMPLETE or FIXING
```

- Never route around a failed node or mark it complete with known failures.
- A failure caused by an unmet dependency routes back to that dependency; downstream changes pause.
- A proposed fix that requires forbidden or later-phase functionality is rejected. Record the limitation and request direction.
- Missing credentials, unavailable infrastructure, an ambiguous destructive action, or a required scope decision moves the node to `BLOCKED`; do not invent values or broaden scope.
- Preserve unrelated user changes and never use destructive Git recovery to resolve a node failure without explicit approval.

## Phase 1 acceptance criteria

Phase 1 is complete only when all nodes are `COMPLETE` and evidence confirms that:

- the FastAPI application imports and starts;
- typed configuration is environment-driven and no secrets are committed;
- PostgreSQL connectivity and SQLAlchemy session infrastructure work as documented;
- Alembic upgrade/downgrade paths are validated against an isolated database;
- foundation Pydantic schemas enforce documented constraints;
- liveness and readiness APIs behave correctly in success and failure cases;
- the full relevant test suite passes;
- Docker and Docker Compose build and reach healthy state from a clean checkout;
- documentation matches actual behavior and cross-references resolve;
- no forbidden Phase 2 or later capability has been implemented;
- each logical node is represented by a focused commit and the working tree is understood.

## Stop conditions

Stop the current node immediately when validation is failing, a secret may be exposed, unrelated work would be overwritten, a destructive action lacks approval, or completion requires out-of-scope technology. Fix the in-scope issue or report the blocker before proceeding.

After `P1-11` passes, **stop the phase**. Report completed nodes, tests, migrations, Docker status, Git commits, known limitations, and the recommended next phase. Do not begin Writing Evaluation, Planner, Memory, LLM, or any other later-phase work without explicit instruction.
