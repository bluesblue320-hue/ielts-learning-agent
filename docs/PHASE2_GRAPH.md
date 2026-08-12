# Phase 2 Development Graph

## Purpose and authority

This document defines **what** may be implemented in Phase 2 and the dependency
order for the Writing Evaluation Pipeline. [DEVELOPMENT_LOOP.md](DEVELOPMENT_LOOP.md)
defines **how** to execute each selected node. The completed
[PHASE1_GRAPH.md](PHASE1_GRAPH.md) remains the historical Phase 1 execution
record.

Creating this graph authorizes the Phase 2 scope but does not implement Phase 2
runtime behavior. `P2-01` is the first `READY` node. Every later node remains
`NOT_STARTED` until all of its dependencies are `COMPLETE`.

## Phase objective

Phase 2 delivers one reliable writing-evaluation path inside the existing
application:

```text
IELTS Writing Task 2 question
+ essay
  -> request validation
  -> Writing Evaluation Service
  -> LLM Provider protocol
  -> structured provider output
  -> Pydantic validation
  -> atomic PostgreSQL persistence
  -> API response
```

The application remains one application with deterministic services and one
provider abstraction. Phase 2 does not introduce an agent loop or multiple
agents.

## Scope boundary

Phase 2 includes:

- deterministic CI that does not require a live provider key;
- Writing Task 2 request and evaluation schemas;
- `WritingAttempt` and `WritingEvaluation` persistence;
- an Alembic migration for the writing tables;
- an LLM provider protocol and deterministic fake provider;
- a DeepSeek provider configured only by environment variables;
- a Writing Evaluation Service with validated structured output;
- deterministic product-score aggregation from criterion scores;
- atomic evaluation persistence;
- `POST /writing/evaluate`;
- bounded, justified retry and explicit failure behavior;
- automated, integration, Docker, and documentation validation.

The following are explicitly forbidden in Phase 2: Learner State update logic,
Learning Memory, Planner, Reflection, Agent Runtime or Agent Loop, LangGraph,
LangChain, RAG, pgvector, Redis, Speaking, Reading, Listening, multi-agent
architecture, frontend implementation, and fine-tuning.

## Architecture and domain rules

1. The evaluator depends on an LLM provider interface or protocol, never on the
   DeepSeek implementation directly.
2. Automated tests use a deterministic fake provider and never require a real
   API key or live network call.
3. DeepSeek credentials and model configuration come from environment variables;
   real credentials are never committed or placed in CI workflows.
4. Provider output entering application logic is structured and validated with
   Pydantic before it can be persisted or returned.
5. Evaluation criteria represent Task Response, Coherence and Cohesion, Lexical
   Resource, and Grammatical Range and Accuracy. Existing IELTS half-band
   validation is reused where appropriate.
6. Any product evaluation band derived from criterion scores uses a documented,
   deterministic, tested aggregation policy. It is not described as an exact
   reproduction of the official final IELTS Writing band unless independently
   verified.
7. Word count is computed deterministically and may be evaluation evidence. An
   essay is not rejected merely because it contains fewer than 250 words.
8. No successful evaluation record is written unless provider output has passed
   validation. Attempt/evaluation transaction boundaries and rollback behavior
   are explicit; persistence failure cannot produce a reported success.
9. Retries are bounded and limited to justified transient provider failures.
   Validation errors and deterministic database failures are not blindly retried.
10. Phase 1's isolated PostgreSQL `test-db` remains the only database used by
    database and migration tests.

## Node states and failure gate

Each node has one state:

```text
NOT_STARTED -> READY -> ACTIVE -> VERIFYING -> COMPLETE
                         |          |
                         v          v
                       FIXING <-----+

Any state -> BLOCKED when required input or authority is unavailable.
```

A node becomes `READY` only when every declared dependency is `COMPLETE`. A
failed implementation, test, migration, integration, Docker, security, or
documentation check keeps the current node in `FIXING`; it does not unlock any
dependent node. Only one node should be `ACTIVE` at a time.

## Dependency graph

```text
P2-01 Phase 2 Baseline and CI
  -> P2-02 Writing Domain Schemas

P2-02
  -> P2-03 Writing Persistence Models
  -> P2-05 LLM Provider Contract

P2-03
  -> P2-04 Alembic Writing Migration

P2-05
  -> P2-06 DeepSeek Provider
  -> P2-07 Writing Evaluator

P2-02 + P2-04 + P2-07
  -> P2-08 Evaluation Persistence Service

P2-06 + P2-08
  -> P2-09 Writing Evaluation API

P2-06 + P2-07 + P2-08 + P2-09
  -> P2-10 Failure and Retry Handling

P2-10
  -> P2-11 Automated Test Suite

P2-04 + P2-11
  -> P2-12 Integration Validation

P2-12
  -> P2-13 Docker Validation

P2-13
  -> P2-14 Documentation

P2-14
  -> P2-15 Final Phase Audit

P2-15 -> STOP
```

This graph is authoritative. In particular, the API cannot begin before the real
provider implementation and atomic persistence path are complete, and no final
validation node can route around a failed deterministic or integration test.

## Nodes and acceptance gates

### P2-01 — Phase 2 Baseline and CI

- **Purpose:** Reconfirm the merged Phase 1 baseline and establish deterministic
  GitHub CI before adding Writing behavior.
- **Dependencies:** Phase 1 complete; no Phase 2 node dependency.
- **Inputs:** Merged `master`, Phase 1 tests, existing Docker/test database
  topology, `pyproject.toml`, and this graph.
- **Deliverables:** Minimal GitHub Actions workflow and any strictly necessary
  test command documentation; no provider credential and no Writing runtime code.
- **Required validation:** Run the existing Phase 1 suite; validate workflow
  syntax and triggers; confirm CI tests use no DeepSeek key or live provider; use
  isolated PostgreSQL when integration tests run.
- **Acceptance condition:** A clean checkout can run deterministic foundation
  checks in CI, required tests pass, and no secret or Phase 2 runtime behavior is
  introduced.
- **Failure routing:** Workflow, dependency, or test failure keeps `P2-01` in
  `FIXING`; capture evidence, make the smallest baseline/CI correction, and rerun
  all P2-01 checks before `P2-02` can become `READY`.

### P2-02 — Writing Domain Schemas

- **Purpose:** Define the typed HTTP/domain boundaries for a Task 2 submission,
  criterion evidence, validated provider output, and evaluation response.
- **Dependencies:** `P2-01`.
- **Inputs:** Existing `BandScore`, the four IELTS Task 2 criteria, conceptual
  request/response shapes, deterministic word-count rule, and aggregation policy
  requirements.
- **Deliverables:** Pydantic v2 schemas for submission, provider result,
  criterion-level feedback, and API result; a documented deterministic word-count
  function or schema-adjacent domain utility if needed.
- **Required validation:** Test valid and invalid requests; blank question/essay;
  essays below 250 words remain valid; deterministic word counts; missing fields;
  mutable-default safety; all criterion bands and derived band inputs use valid
  0–9 half-band increments.
- **Acceptance condition:** Schemas express the exact Phase 2 boundary without
  evaluation, provider, database, learner-state, or agent behavior, and all domain
  constraints have focused tests.
- **Failure routing:** Any ambiguous field contract or failed schema test keeps
  `P2-02` in `FIXING`; downstream model and provider work remains locked until
  schemas and tests agree.

### P2-03 — Writing Persistence Models

- **Purpose:** Represent writing attempts and validated evaluations using focused
  SQLAlchemy 2.x models.
- **Dependencies:** `P2-02`.
- **Inputs:** Accepted writing schemas, current declarative `Base`, PostgreSQL,
  and required `WritingAttempt`/`WritingEvaluation` concepts.
- **Deliverables:** Models for `WritingAttempt` (`id`, question, essay,
  deterministic `word_count`, `created_at`) and `WritingEvaluation` (attempt
  reference, criterion/product bands, structured evidence and feedback, provider,
  model, prompt version, `created_at`), with explicit constraints and relationship.
- **Required validation:** Import metadata; inspect tables, columns, foreign keys,
  constraints, relationships, defaults, and cascade choices; verify SQLAlchemy 2.x
  `Mapped`/`mapped_column` patterns; confirm no learner-state columns or behavior.
- **Acceptance condition:** Models faithfully persist accepted Phase 2 data, make
  ownership and integrity explicit, and contain no service or provider logic.
- **Failure routing:** Model/metadata mismatch returns `P2-03` to `FIXING`; no
  migration may begin until model structure and constraints pass review.

### P2-04 — Alembic Writing Migration

- **Purpose:** Create a reproducible, reversible PostgreSQL schema transition for
  the writing models.
- **Dependencies:** `P2-03`.
- **Inputs:** Accepted SQLAlchemy metadata, baseline revision `0001_phase1`, and
  isolated `test-db`.
- **Deliverables:** One focused Alembic revision creating writing attempts and
  evaluations with required constraints, indexes, foreign key, upgrade, and
  downgrade behavior.
- **Required validation:** Confirm one Alembic head; upgrade from Phase 1 head;
  inspect resulting schema; downgrade to `0001_phase1`; re-upgrade; compare model
  and migration intent; run only against isolated test PostgreSQL.
- **Acceptance condition:** A clean Phase 1 database reaches the writing schema
  and reverses without manual steps or touching the development database.
- **Failure routing:** Migration, downgrade, schema, or isolation failure keeps
  `P2-04` in `FIXING` and blocks persistence services and integration validation.

### P2-05 — LLM Provider Contract

- **Purpose:** Decouple writing evaluation from any provider vendor and provide a
  deterministic test seam.
- **Dependencies:** `P2-02`.
- **Inputs:** Accepted structured provider-output schema, evaluator needs, timeout
  and error categories, and secret-safe configuration rules.
- **Deliverables:** A minimal typed provider protocol/interface, provider request
  boundary, normalized provider exceptions, and deterministic fake provider for
  tests.
- **Required validation:** Type/import tests; fake-provider success and injected
  failure tests; prove evaluator-facing code need not import DeepSeek; ensure the
  contract returns structured data subject to Pydantic validation.
- **Acceptance condition:** Evaluator tests can run deterministically without a
  network, API key, vendor SDK, or DeepSeek implementation.
- **Failure routing:** Leaky vendor coupling, nondeterminism, or unclear errors
  keeps `P2-05` in `FIXING`; both `P2-06` and `P2-07` remain locked.

### P2-06 — DeepSeek Provider

- **Purpose:** Implement the real provider behind the accepted provider contract.
- **Dependencies:** `P2-05`.
- **Inputs:** Provider protocol, DeepSeek HTTP/API contract, structured output
  schema, environment configuration, timeout policy, model and prompt-version
  identifiers.
- **Deliverables:** A focused DeepSeek provider adapter and typed, secret-safe
  settings for endpoint/model/key/timeout; no key in source, examples, logs, or CI.
- **Required validation:** Mocked HTTP success, timeout, HTTP error, empty response,
  malformed payload, and missing-field tests; configuration validation and secret
  masking; optional local live smoke test only when a user-supplied key exists.
- **Acceptance condition:** The adapter satisfies the provider contract, emits
  normalized failures, never bypasses structured validation, and deterministic
  tests require no live DeepSeek access.
- **Failure routing:** Provider contract, security, or deterministic test failure
  keeps `P2-06` in `FIXING`; the API and failure-handling nodes remain locked.

### P2-07 — Writing Evaluator

- **Purpose:** Orchestrate deterministic submission evidence and qualitative
  evaluation through the provider contract.
- **Dependencies:** `P2-05`.
- **Inputs:** Writing schemas, four criterion definitions, deterministic word
  count, provider protocol, validated provider result, and aggregation rules.
- **Deliverables:** Writing Evaluation Service that constructs the versioned
  provider request, validates output, and deterministically derives the product
  evaluation band from criterion bands without blindly trusting a provider total.
- **Required validation:** Fake-provider tests for all four criteria, strengths,
  weaknesses, error tags, recommended skills, feedback, prompt/provider metadata,
  below-250-word essays, invalid bands, and aggregation boundary/rounding cases.
- **Acceptance condition:** The service is vendor-independent, deterministic
  outside the provider call, returns only validated output, and makes no claim of
  reproducing the official final IELTS Writing band.
- **Failure routing:** Validation, aggregation, prompt-contract, or coupling
  failure keeps `P2-07` in `FIXING`; persistence and API nodes remain locked.

### P2-08 — Evaluation Persistence Service

- **Purpose:** Persist the attempt and its validated evaluation atomically.
- **Dependencies:** `P2-02`, `P2-04`, `P2-07`.
- **Inputs:** Accepted models/migration, validated evaluator result, SQLAlchemy
  session infrastructure, and explicit transaction requirements.
- **Deliverables:** Focused persistence/application service that records the
  attempt and evaluation in one explicit transaction and returns persisted IDs.
- **Required validation:** Integration tests for successful write, relationships,
  stored structured fields, invalid evaluation before write, flush/commit failure,
  rollback, and absence of a successful evaluation after any failure.
- **Acceptance condition:** Only validated evaluations are persisted; failure
  never reports success or leaves a partial attempt/evaluation pair.
- **Failure routing:** Atomicity, rollback, or database test failure keeps `P2-08`
  in `FIXING`; the API and later reliability nodes remain locked.

### P2-09 — Writing Evaluation API

- **Purpose:** Expose the complete writing-evaluation use case through one thin
  FastAPI endpoint.
- **Dependencies:** `P2-06`, `P2-08`.
- **Inputs:** Request/response schemas, evaluator and persistence services,
  provider construction/configuration, and database dependency.
- **Deliverables:** `POST /writing/evaluate`, dependency wiring, explicit response
  schema including `attempt_id` and evaluation, and appropriate HTTP status
  mapping without internal or credential leakage.
- **Required validation:** `httpx` tests with fake provider for valid request,
  blank input, below-250-word essay acceptance, response schema, persisted record,
  and dependency failures; verify the route contains no evaluation logic.
- **Acceptance condition:** One request can traverse validation, evaluation,
  atomic persistence, and response using a deterministic fake provider, while
  preserving thin route boundaries.
- **Failure routing:** HTTP contract, dependency, persistence, or leakage failure
  keeps `P2-09` in `FIXING`; failure/retry consolidation cannot begin.

### P2-10 — Failure and Retry Handling

- **Purpose:** Make failure behavior explicit across provider, validation,
  persistence, and API boundaries.
- **Dependencies:** `P2-06`, `P2-07`, `P2-08`, `P2-09`.
- **Inputs:** Normalized provider errors, evaluator validation errors, transaction
  failures, API mappings, and bounded retry requirements.
- **Deliverables:** Documented error taxonomy and minimal retry policy covering
  provider timeout, transient provider HTTP failure, malformed structured output,
  missing required fields, invalid IELTS bands, empty response, and database
  failure; bounded retry implementation only where justified.
- **Required validation:** Deterministic tests for every listed failure, retryable
  versus non-retryable classification, maximum attempts, no unbounded loop,
  rollback/no-success persistence, stable safe API responses, and no secret or raw
  provider-body leakage.
- **Acceptance condition:** Each required failure has a predictable outcome;
  retries are bounded and restricted to transient provider failures; validation
  and database failures do not create duplicate or partial success.
- **Failure routing:** Any unhandled failure, unsafe retry, data duplication, or
  information leak keeps `P2-10` in `FIXING` and blocks suite consolidation.

### P2-11 — Automated Test Suite

- **Purpose:** Consolidate deterministic coverage for all completed Phase 2
  behavior while preserving Phase 1 coverage.
- **Dependencies:** `P2-10`.
- **Inputs:** All unit/API/integration tests from `P2-02` through `P2-10`, fake
  provider, Phase 1 tests, and CI commands.
- **Deliverables:** Organized deterministic test suite and documented markers or
  fixtures; normal suite and CI require no real provider key.
- **Required validation:** Run targeted suites and full pytest; confirm no required
  skips in configured full validation; run without DeepSeek credentials and prove
  no live provider request occurs; retain explicit skips only when isolated test
  PostgreSQL is intentionally absent locally.
- **Acceptance condition:** Every completed Phase 2 node and all Phase 1 behavior
  have useful deterministic coverage with visible failures and no secret/network
  dependency.
- **Failure routing:** Flaky, skipped-required, live-network, or regression failure
  keeps `P2-11` in `FIXING`; integration validation remains locked.

### P2-12 — Integration Validation

- **Purpose:** Verify the end-to-end service and persistence path against isolated
  PostgreSQL with a deterministic provider.
- **Dependencies:** `P2-04`, `P2-11`.
- **Inputs:** Full application, writing migration, fake provider, isolated
  `test-db`, and integration fixtures.
- **Deliverables:** Integration evidence for submission through API response,
  stored attempt/evaluation, migration state, rollback paths, and development
  database isolation.
- **Required validation:** Apply migrations to `test-db`; execute successful and
  failing writing flows; inspect stored rows and metadata; verify failed
  validation/persistence creates no successful evaluation; confirm development DB
  revision/data is unchanged.
- **Acceptance condition:** The target flow works against PostgreSQL without a live
  LLM and all transaction/isolation guarantees are evidenced.
- **Failure routing:** End-to-end, migration, atomicity, or isolation failure keeps
  `P2-12` in `FIXING`; Docker validation remains locked.

### P2-13 — Docker Validation

- **Purpose:** Prove the complete deterministic Phase 2 workflow is reproducible
  in the existing container environment.
- **Dependencies:** `P2-12`.
- **Inputs:** Dockerfile, Compose stack, isolated `db`/`test-db`, migrations, API,
  and deterministic test suite.
- **Deliverables:** Minimal Docker/Compose changes if required and recorded clean
  checkout validation evidence; no provider key embedded in an image or required
  by the test container.
- **Required validation:** `docker compose config`; build runtime/test targets;
  healthy `db`, `test-db`, and API; migration completion; full containerized test
  suite; writing API smoke test with deterministic provider configuration; clean
  teardown; inspect rendered configuration and image inputs for credentials.
- **Acceptance condition:** A documented clean Docker workflow validates the full
  Phase 2 path with isolated test data and no real DeepSeek credential.
- **Failure routing:** Build, health, migration, test, isolation, or credential
  failure keeps `P2-13` in `FIXING`; documentation cannot be finalized.

### P2-14 — Documentation

- **Purpose:** Synchronize developer and API documentation with verified Phase 2
  behavior and limitations.
- **Dependencies:** `P2-13`.
- **Inputs:** Verified schemas, endpoint, environment variables, aggregation and
  retry policies, migrations, tests, Docker workflow, and live-provider limits.
- **Deliverables:** Accurate README/local-development/API/architecture/phase-graph
  updates as required, secret-safe DeepSeek setup, deterministic test commands,
  failure behavior, and explicit product-score disclaimer.
- **Required validation:** Execute documented commands where practical; resolve
  links; compare every runtime claim with code/tests; verify no real key or CI
  claim is unsupported; confirm Phase 2 exclusions remain explicit.
- **Acceptance condition:** A new developer can understand and validate the
  implemented pipeline, while documentation neither overstates IELTS equivalence
  nor claims unverified live-provider behavior.
- **Failure routing:** Broken command, link, secret, or unsupported claim keeps
  `P2-14` in `FIXING`; final audit remains locked.

### P2-15 — Final Phase Audit

- **Purpose:** Decide whether the whole Phase 2 graph satisfies its objective and
  stop boundary.
- **Dependencies:** `P2-14`.
- **Inputs:** All node commits and evidence, full test results, migration and
  database-isolation results, Docker results, documentation, and repository diff.
- **Deliverables:** Final audit record covering completed nodes, tests, CI,
  migrations, provider abstraction, deterministic evaluation, persistence/API,
  failures, Docker, security, known limitations, commits, and next-phase
  recommendation.
- **Required validation:** Re-run full deterministic local and containerized
  suites; one-head migration upgrade/downgrade/re-upgrade; end-to-end fake-provider
  request; failure/rollback matrix; health APIs; CI status; link and secret scans;
  forbidden-scope scan; clean Git review.
- **Acceptance condition:** Every node `P2-01` through `P2-15` is `COMPLETE`, and
  question plus essay reliably produces a validated, atomically persisted
  evaluation and API response without Phase 3 behavior or mandatory live LLM
  access.
- **Failure routing:** Any failed or missing evidence routes to the owning Phase 2
  node in `FIXING`. `P2-15` cannot complete and `STOP` cannot be reached until the
  dependency is repaired and all relevant validation is rerun.

## Phase 2 acceptance criteria

Phase 2 is complete only when all nodes are `COMPLETE` and evidence confirms:

- `POST /writing/evaluate` validates a Task 2 question and essay without rejecting
  an essay solely for being under 250 words;
- word count and any product evaluation band are deterministic and tested;
- all four Task 2 criterion results use validated structured schemas;
- the evaluator depends only on the provider protocol and deterministic tests use
  a fake provider;
- DeepSeek configuration is environment-based, secret-safe, and unnecessary for
  normal automated tests;
- malformed, missing, empty, invalid-band, timeout, HTTP, and database failures
  have bounded, documented behavior;
- only validated evaluations are atomically persisted in PostgreSQL;
- migrations upgrade, downgrade, and re-upgrade on isolated `test-db`;
- Phase 1 tests and health APIs remain passing;
- CI, local, integration, and Docker validations are deterministic and pass;
- documentation matches the verified implementation and does not overstate score
  equivalence or live-provider validation;
- no forbidden later-phase capability has been implemented.

## Execution and stop rule

For each selected node, follow the existing sequence in
[DEVELOPMENT_LOOP.md](DEVELOPMENT_LOOP.md):

```text
Observe -> Select -> Plan -> Implement -> Test -> Review -> Fix -> Commit -> Repeat
```

Do not skip a failed check, combine nodes to route around a dependency, or unlock
a downstream node early. After `P2-15` is complete, **STOP**. Do not begin learner
state, memory, planning, agent runtime, another IELTS skill, or any later phase
without a new explicit authorization and phase graph.
