# Phase 10 Internal Implementation Audit

## Audit result

**P10-18 = INTERNAL_AUDIT_COMPLETE**

**Phase 10 External Implementation Review = APPROVED**

**Phase 10 PR = READY_TO_OPEN**

**Phase 10 = AWAITING_PR_VALIDATION**

The internal audit remains complete, and External Implementation Review has now
returned APPROVED. This approval authorizes PR creation and validation; it is
not Phase 10 completion or merge authorization.

## Repair finding and audited scope

External Implementation Review returned `FIXING_REQUIRED` because the canonical
corpus, individual evaluators, runner, reporting, and gate existed but were not
connected by an official executable path. The repair was audited through
implementation/documentation commit
`6ca7c52f46f307e8a3754fff372508a9ada33724` on
`phase/10-writing-evaluation-calibration-v1`. The merge base remains the Phase 9
merge commit `75a667ff4ce16b79e7d4ba517081e1bd3d96fd57`.

The re-audit inspected the frozen policy and graph, canonical fixtures,
`app/eval/`, real Phase 1–9 service paths, Eval tests, full backend/web/browser
validation, Alembic integrity, changed files, and GitHub Actions run
`33160887212`.

## Canonical execution path

The official internal path is:

```text
writing-eval-regression-corpus-v1
→ strict official executor registry
→ isolated real deterministic application paths
→ actual applicable evaluators
→ EvalRunner
→ RunnerSuiteResult
→ StructuredEvalReport
→ Markdown report
→ gate exit status
```

`app/eval/regression_runtime.py` owns the canonical registry and requires no
operator-supplied executor mapping. Registry validation rejects duplicate,
missing, and unknown case IDs before execution. Current corpus and registry
coverage is exactly 11 / 11.

Every database-backed case runs against a URL accepted by
`validate_test_database_url`. Alembic upgrades that disposable database to head,
and the runtime truncates the complete Writing/learning/practice table set with
identity reset before and after each case. The integration test proves the
suite leaves zero WritingAttempt, LearningUpdate, and WritingPractice rows.

Provider cases use only frozen JSON payloads and deterministic internal protocol
adapters. The runtime removes/does not require `IELTS_DEEPSEEK_API_KEY`; no live
provider or network request occurs.

## Case and evaluator evidence

The actual canonical run produced 11 PASS, zero FAIL, zero BLOCKED, and zero
INVALID_CASE. Applicable evaluator execution is:

| Evaluator | Canonical cases |
| --- | ---: |
| Outcome | 10 |
| Authority | 7 |
| Lifecycle | 4 |
| Trajectory | 1 |
| Knowledge grounding | 1 |

Executors invoke the real `WritingEvaluationService`, application-owned product
band normalization, `RetryingProvider`, `apply_writing_evaluation`, canonical
State rebuild, Memory episode queries and Planner v2 audit projection,
`PracticeGenerationService`, stale Agent fence, `AgentTurnExecutor`, Phase 9
Knowledge retrieval/provenance, and the two-episode authoritative lifecycle as
applicable. Findings come from the real Outcome, Authority, Lifecycle,
Trajectory, and Knowledge evaluators.

Historical bad input is handled as expected-failure evidence: the underlying
Knowledge evaluator must return the exact `knowledge_unknown_id` VETO before
the regression case may pass. A test forces a real Outcome evaluator failure
and proves the canonical suite becomes FAIL; there is no `_passing_executor`
escape path.

One Phase 10 corpus metadata defect was repaired. `practice-stale-fence`
previously declared Trajectory applicability, but the frozen Phase 8 path raises
`AgentStalePracticeError` before any `AgentTurnResponse` exists and the API maps
that to a safe conflict. The case now correctly executes Outcome plus Authority,
verifying the real exception, zero provider calls, unchanged generated practice,
and no attempt link. Agent trajectory remains covered by the real bounded Agent
case.

## Reporting and gate audit

`execute_canonical_regression` derives both `StructuredEvalReport` and stable
Markdown from the same `RunnerSuiteResult`; no second report truth source was
introduced. The audited report has suite status PASS, 11 cases, zero VETO
failures, and no first-failure boundary.

`python -m app.eval.gate` now:

1. requires and validates isolated PostgreSQL;
2. removes an inherited provider secret;
3. runs bounded Eval framework self-tests;
4. executes the official canonical runtime;
5. emits the human report derived from the structured report;
6. returns zero only for PASS.

Gate tests prove PASS → 0 and FAIL / BLOCKED / INVALID_CASE → nonzero.
Self-test failure and unexpected registry/database/runtime infrastructure
failure also return nonzero. A passing pytest self-test result cannot override a
non-passing canonical suite.

## Validation evidence

All results below are from the 2026-08-28 repair validation.

| Validation | Result |
| --- | --- |
| Canonical runtime | 11 / 11 cases PASS; zero VETO, FAIL, BLOCKED, or INVALID_CASE |
| Canonical runtime integration | 4 passed, including repeatability, isolation, evaluator tracking, and forced-failure proof |
| Complete deterministic Eval surface | 89 passed, zero skipped |
| Final local gate | 73 self-tests passed, then canonical suite PASS 11 / 11; exit 0 |
| Complete backend | 1131 passed; one Starlette/httpx dependency deprecation warning |
| Python lint | Ruff passed on all changed Python files |
| Alembic | head check; downgrade to base; upgrade to `0006_submission_claim_recovery`; head check — successful |
| Web lint | successful |
| TypeScript typecheck | successful |
| Web unit tests | 15 passed |
| Next.js production build | successful; 9 routes generated/classified |
| Playwright | 6 passed |
| GitHub Actions | run `33160887212` SUCCESS; canonical gate, backend, web quality gates, Playwright all successful |

The first Playwright invocation used the system Python and could not import
Alembic. Rerunning through the repository-supported `PYTHON` override pointing
to `.venv` succeeded with 6 / 6 tests; this was an environment selection issue,
not a product or test failure.

## Frozen-contract and scope audit

The repair did not change `writing-task2-v1`, scoring, Learner State, Memory,
Planner, Practice, Knowledge, or Agent authority/bounds. It introduced no
migration, table, dependency, public `/eval` API, dashboard, provider
abstraction, production trace, external Eval framework, calibration labels, or
live calibration.

No LangChain, LangGraph, vector database, Redis, Celery, Kafka, runtime web
search, multi-agent behavior, Reading, Listening, Speaking, authentication,
payments, P10-19, or Phase 11 work was added. No secret, personal production
data, or uncontrolled network dependency was introduced. At the time of the
internal audit, no PR was opened and nothing was merged.

The canonical calibration corpus truthfully remains at zero admissible cases
with `no_admissible_reference_data`. The project still makes no examiner-grade
accuracy, bias, or provider-quality claim. No canonical live provider capture
exists; replay continues to demonstrate the fail-closed zero-reference path.

GitHub Actions emitted one non-failing platform annotation that pinned actions
targeting Node.js 20 are being forced onto Node.js 24. The backend retains one
non-failing Starlette/httpx deprecation warning. Neither changes Phase 10
contract evidence.

## Stop gate

P10-12 and P10-15 are COMPLETE, P10-18 is INTERNAL_AUDIT_COMPLETE, and
External Implementation Review is APPROVED. The next authority is PR validation.
PR creation is authorized, but merge is not:

- do not mark Phase 10 COMPLETE;
- do not merge or close the PR;
- do not modify `master`;
- do not start Phase 11.
