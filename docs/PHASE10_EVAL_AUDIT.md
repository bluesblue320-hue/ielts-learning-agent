# Phase 10 Evaluation Surface Audit

## Status

**P10-01 - Existing Evaluation Surface Audit: COMPLETE.** This is a
repository-backed, documentation-only audit. It adds no Eval implementation,
corpus, labels, API, migration, CI change, dependency, or production behavior
change. The scope is frozen Writing Task 2 and writing-task2-v1.

Required Phase 8-10 graphs/audits and Knowledge, Agent, Memory, Planner, and
State policies were read before code inspection. Actual source/tests are the
evidence.

## Evidence map

| Surface | Implementation | Existing test evidence | Classification |
| --- | --- | --- | --- |
| Scoring/provider | writing_evaluation.py; provider.py; deepseek.py; retry.py; rubric/Writing schemas | writing evaluator, provider contract, DeepSeek, retry, Writing API tests | ALREADY_COVERED_DETERMINISTICALLY except live score quality |
| Durable lifecycle | writing persistence, learning application, Writing/Learning models | persistence, Phase 2/3 integration, application, concurrency tests | ALREADY_COVERED_DETERMINISTICALLY |
| State/Memory/Planner | app/learner and app/memory | state engine, memory, planner, Phase 7 tests | ALREADY_COVERED_DETERMINISTICALLY locally |
| Practice/Knowledge/Agent | practice services, knowledge, guidance, agent | practice, Phase 9 grounding, Knowledge/guidance, Agent tests | mixed; see below |
| Product/CI | API routes, web/e2e, CI workflow | httpx/FastAPI and Playwright | PARTIALLY_COVERED |

Commands run: git status --short; git branch --show-current; git log --oneline
-5; git remote -v; rg discovery; source/test inspection; python -m pytest -q
--strict-markers.

The pytest command did not run tests: active interpreter
C:\Users\30306\anaconda3\python lacks fastapi and alembic, causing 30
collection errors. This audit claims no local passing result. No test,
dependency, or config was changed; CI is the reproducible configured runner.

## Scoring and provider boundary

POST /writing/evaluate validates WritingSubmission, injects LLMProvider, calls
WritingEvaluationService, then persists atomically. The request builder owns
rubric/prompt versions, criterion definitions, descriptors, half-band and
length guidance, word count, scoring policy, output schema, metadata, and
safety constraints. The question/essay are untrusted. ProviderEvaluationPayload
owns qualitative criterion bands/evidence/feedback only.

aggregate_product_band deterministically uses four validated half-bands, equal
weights, and Decimal half-up rounding; provider output cannot override the
product band. Evaluator/provider tests cover invalid bands, metadata/product
override, malformed payload, HTTP/timeouts/network/JSON/missing-fields,
normalized failure, and bounded retry (maximum three attempts).

FakeProvider records scripted payloads/errors, FakePracticeGenerator supplies
policy-valid content, and tests/conftest.py prevents live provider HTTP. These
are reusable for deterministic regression, not proof of live score stability.

## Durable lifecycle and planning evidence

WritingSubmission -> WritingEvaluationResult -> WritingAttempt/WritingEvaluation
-> LearningUpdate + 4 LearningEvidence + 4 LearnerSkillState
-> PracticeRecommendation

WritingEvaluationPersistenceService validates before write and rolls back.
apply_writing_evaluation locks learner ownership, uses unique
LearningUpdate.writing_evaluation_id for idempotency, reuses same-owner results,
rejects cross-owner use, rebuilds durable state, and has no provider call in its
transaction. Persistence, application, concurrency, and Phase 3 tests prove
row accounting, rollback, idempotency, conflict, and canonical replay.

test_state_engine.py proves writing-state-ewma-v1 exact Decimal arithmetic,
half-band handling, created-at/id chronology, late-arrival rebuild, and
repeatability. app/memory and its query/atom/profile/API tests prove L0/L1/L2/L3
source identity, learner isolation, trend/gap/recency, and read-only/provider-
free behavior. Planner and memory-planner tests prove v1/v2 terminal branches,
exact ties, and persistent gap -> trend -> recency -> canonical priority.

The full Evaluation -> apply -> State -> Memory -> v2 Planner path is
PARTIALLY_COVERED: its invariants are inferred across tests, but no current
canonical evaluator emits one mode-labelled verdict and first failing boundary.
Existing durable rows and response structures are sufficient test-side evidence;
no production instrumentation is proven necessary.

Chronology must stay purpose-specific: State uses WritingAttempt created_at ASC,
id ASC; Memory lists LearningUpdate created_at DESC, id DESC; Agent/guidance
current state uses LearningUpdate.id DESC.

## Practice, Knowledge, and Agent

Practice tests prove recommendation ownership, generation idempotency,
no-practice no-op, provider failure behavior, fingerprint replay/conflict,
claim recovery, stale fences, concurrency, and completion/replan. Completion is
PARTIALLY_COVERED as a reusable Phase 10 trajectory; generated-practice quality
is TOO_SUBJECTIVE_FOR_DETERMINISTIC_VERIFICATION and
REQUIRES_CALIBRATION_REFERENCE_DATA.

Phase 9 snapshot/retriever/descriptor/compatibility/grounding/guidance tests
prove Knowledge IDs/locators, bounded deterministic retrieval,
application-owned citations, injection rejection, and safe chronology. Knowledge
cannot redefine scoring or choose the Planner target. That complete
cross-layer authority proof is PARTIALLY_COVERED.

Agent executor bounds are: mutating tools 3, observations 4, provider-backed
calls 2, automatic generations 1, automatic completions 1. AgentTurnResponse
provides initial/final observations, closed AgentStep tool/outcome sequence,
stop_reason, recommendation, and practice. Agent schema/selector/observation/
executor/tools/API tests cover sequences, re-observation, replay, generation,
completion, conflicts, provider budget, ownership, and bounds. Trajectory Eval
must use this structured evidence plus durable freshness/chronology/ownership,
never free text or private reasoning.

## API, browser, fixtures, and CI

FastAPI tests cover Writing, learning, practice, Memory, guidance, and Agent.
Browser tests are product evidence, not automatic proof of all backend semantics:
closed-loop covers an adaptive loop; Phase 6 history/progress/resume; Phase 7
v1/v2 rendering; Phase 8 Agent continuation; Phase 9 citations after reload.

CI uses Ubuntu 24.04, Python 3.12, PostgreSQL 17, python -m pytest -q
--strict-markers, web lint/typecheck/unit/build, and Playwright E2E. It has an
isolated test database and no real LLM key. The future deterministic gate fits
as a provider-free pytest command alongside current tests; live calibration must
not gate merge.

## Historical regression candidates

| Candidate | Current protection | Future use |
| --- | --- | --- |
| Provider metadata/product-band override and malformed payload | evaluator tests; 9565647 | deterministic contract |
| Retry/no write before final outcome | retry/Writing API tests | provider-boundary |
| Late arrival/concurrency canonical state | state/application/concurrency tests | cross-layer replay |
| v2 exact-tie and v1/v2 reconstruction | Phase 7/planner tests | outcome/trajectory |
| Claim recovery/different fingerprint/stale practice | Phase 8, practice/Agent tests; af00c4f, a046891 | authority/fail-closed |
| Rubric/Knowledge ledger and citations | Phase 9 tests; 58cf487, 738b430 | Knowledge grounding |

## Required questions and recommendation

1. Existing tests enforce strict contracts, aggregation, retry/failure, rollback,
ownership/idempotency, Decimal state, Memory/Planner, practice lifecycle,
Knowledge/citations, and Agent bounds.
2. Missing: a canonical evaluator across provider fixture/capture, lifecycle,
State, Memory, Planner, grounded practice, and Agent response.
3. Existing observable evidence: WritingEvaluationResult, returned IDs,
LearningUpdate/evidence/state/recommendation rows, planner snapshot, Memory,
PracticeResponse, and AgentTurnResponse.
4. Minimum v1 needs no proven instrumentation; use test-side collection. P10-02
may permit only test-only non-semantic exposure if needed.
5. Deterministic alternatives: FakeProvider, FakePracticeGenerator, injected
HTTP, and the live-network guard.
6. Prompt/private-envelope/UI-copy tests can be implementation details unless a
frozen policy owns them; use structured/durable assertions.
7. The table lists historical candidates; no cases/labels are created.
8. No calibration corpus, raw labels, rater provenance/adjudication, agreement
metric, or captured live run exists.
9. Existing GitHub Actions Python/PostgreSQL CI can run deterministic regression.
10. Smallest v1: pytest-integrated cross-layer checks using existing fakes,
isolated PostgreSQL, AgentTurnResponse, and JSON/report artifacts.

Deterministic Regression Mode uses fake/captured payloads and existing structured
evidence. Live Calibration Mode needs real essays/provider scores plus
independent raw human/reference scores, provenance, disagreement/adjudication,
and agreement/bias/variance. Calibration Replay Mode recomputes reports from
captured outputs/labels without another provider call.

contract correctness != reference-score agreement
provider variance != code regression

### REUSE

- Existing pytest/CI PostgreSQL, fakes, network guard, migrations, factories,
  structured results, durable rows, Memory/Planner, Knowledge, and Agent response.

### NEED_NEW (after P10-02 freeze)

- Separate versioned regression-case/result and calibration/reference-label schemas.
- Test-side runner/evaluators, first-failure attribution, JSON/report artifacts.
- Calibration corpus with raw labels, provenance, disagreement/adjudication,
  captured provider metadata, and replay inputs.

### DO_NOT_BUILD

- Public Eval API/dashboard, production trace table, migration, generic framework,
  vector DB/RAG, LangChain/LangGraph, Redis/Celery/Kafka, or live-provider CI gate.
- Any scoring, rubric, Planner, Memory, Agent, or Knowledge semantic change.

P10-01 is complete. P10-02 is the sole next READY design node; formal External
Design Review remains pending P10-02, and P10-03/implementation remain unauthorized.
