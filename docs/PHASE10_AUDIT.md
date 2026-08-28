# Phase 10 Internal Implementation Audit

## Audit result

**P10-18 = RE_AUDIT_REQUIRED**

**Phase 10 External Implementation Review = FIXING_REQUIRED**

**Phase 10 = EXTERNAL_REVIEW_REPAIR**

The external review found that the canonical corpus is not yet connected to
official real executors, `EvalRunner`, reporting, and the CI gate. The prior
internal readiness finding is superseded until P10-12 and P10-15 are repaired
and P10-18 is re-audited. This status is not external approval, Phase 10
completion, PR authorization, or merge authorization.

## Scope and evidence basis

Audit date: 2026-08-28. The audited branch is
`phase/10-writing-evaluation-calibration-v1`. Its merge base with `master` is
`75a667ff4ce16b79e7d4ba517081e1bd3d96fd57`, the Phase 9 merge commit. Batch B
began after milestone-ready commit
`bb92424a218e22ddf531cce4b3da2eb631128f02`; implementation through P10-17 was
inspected at `33d6cab906c8c7ae6f5ca9c9d6e64204d2aced4f`. The P10-18 commit adds only
this audit and synchronized status documentation.

The audit checked the actual branch against:

- `docs/PHASE10_GRAPH.md`;
- `docs/PHASE10_EVAL_AUDIT.md`;
- `docs/WRITING_EVAL_CALIBRATION_POLICY.md`;
- `docs/PHASE10_EVAL_OPERATOR.md`;
- `app/eval/`, the canonical corpora/fixtures, and all Eval tests;
- the complete Phase 1–10 backend, migration, web, and browser validation
  results recorded by P10-16;
- the complete `master...HEAD` changed-file and commit lists.

## Frozen versions

| Contract | Audited identifier |
| --- | --- |
| Policy | `writing-eval-calibration-v1` |
| Regression corpus | `writing-eval-regression-corpus-v1` |
| Calibration corpus | `writing-score-calibration-corpus-v1` |
| Regression case | `writing-eval-regression-case-v1` |
| Calibration case | `writing-score-calibration-case-v1` |
| Reference label | `writing-score-reference-label-v1` |
| Provider capture | `writing-score-provider-capture-v1` |
| Eval result | `writing-eval-result-v1` |
| Calibration result | `writing-score-calibration-result-v1` |
| Failure taxonomy | `writing-eval-failure-taxonomy-v1` |
| Report | `writing-eval-report-v1` |

All identifiers are enforced by strict, frozen Pydantic models. Unknown fields,
unsupported versions, invalid enums, duplicate IDs, unresolved fixtures, and
unsafe capture/promotion fields fail closed.

## P10-01 through P10-17 traceability

| Node | Result | Primary evidence |
| --- | --- | --- |
| P10-01 | COMPLETE / external review APPROVED | `docs/PHASE10_EVAL_AUDIT.md` inventories the real Phase 1–9 surface and gaps. |
| P10-02 | COMPLETE / external design review APPROVED | `docs/WRITING_EVAL_CALIBRATION_POLICY.md` freezes scope, versions, modes, severity, evidence, and CI authority. |
| P10-03 | COMPLETE | `app/eval/schemas.py` defines strict cases, labels, captures, findings, and result contracts. |
| P10-04 | COMPLETE | `app/eval/corpora.py` and `tests/fixtures/eval/` keep regression and calibration truth separate. |
| P10-05 | COMPLETE | `app/eval/outcome.py` checks structured application outcomes. |
| P10-06 | COMPLETE | `app/eval/trajectory.py` checks frozen Agent bounds and structured steps without private reasoning. |
| P10-07 | COMPLETE | `app/eval/knowledge.py` reuses the Phase 9 snapshot, retrieval, sources, IDs, citations, and locators. |
| P10-08 | COMPLETE | `app/eval/authority.py` fails closed for unsafe status, ownership, and authority evidence. |
| P10-09 | COMPLETE | `app/eval/lifecycle.py` plus PostgreSQL integration evidence covers two authoritative episodes, chronology, replay, State, Memory, Planner, recommendation, grounding, and authority. |
| P10-10 | COMPLETE | `app/eval/calibration.py` computes exact Decimal agreement, error, bias, distributions, per-criterion/tier results, exclusions, and human disagreement. |
| P10-11 | COMPLETE | `app/eval/attribution.py` applies frozen first-failure order, status precedence, severity, and deterministic-regression classification. |
| P10-12 | COMPLETE | `app/eval/runner.py` keeps deterministic, live calibration, and replay execution distinct, bounded, and fail-closed. |
| P10-13 | COMPLETE | `app/eval/reporting.py` derives both versioned structured output and stable Markdown from one structured result. |
| P10-14 | COMPLETE | `app/eval/promotion.py` requires approved review, provenance, frozen contract basis, reproduction, before/after proof, and fixtures; it never writes the corpus. |
| P10-15 | COMPLETE | `app/eval/gate.py` and `.github/workflows/ci.yml` provide the isolated, provider-free deterministic gate. |
| P10-16 | COMPLETE | Full validation evidence is recorded below and in `docs/PHASE10_GRAPH.md`. |
| P10-17 | COMPLETE | `docs/PHASE10_EVAL_OPERATOR.md` documents modes, operation, evidence admission, captures, reports, promotion, CI, and limitations. |

## Corpus and evidence audit

Both canonical corpus loaders completed successfully.

- Regression corpus: 11 unique, provenance-backed cases; all referenced files
  resolve. Coverage includes provider contract, product-band ownership, retry,
  idempotent LearningUpdate, late state replay, Memory/Planner exact ties,
  ownership, stale practice, Knowledge provenance, bounded Agent trajectory,
  and a two-episode PostgreSQL learning lifecycle.
- Evaluator applicability across those cases is: outcome 9, authority 7,
  lifecycle 4, trajectory 2, Knowledge grounding 1.
- Calibration corpus: zero cases and zero labels, explicitly declared
  `no_admissible_reference_data`.

Regression expected outcomes are frozen application-contract truth.
Calibration references are separately versioned evidence with provenance,
evidence tier, raw rater identity, ambiguity, and separate adjudication. The
loaders and models do not merge the corpora or turn a score reference into a
production scoring contract.

The zero-reference path is truthful. Calibration analysis and both calibration
runner modes return `blocked` with `insufficient_reference_data` when no
admissible references exist; they do not call a provider, fabricate labels,
emit zero-denominator metrics, or claim examiner-grade accuracy.

Provider captures preserve provider/model, thinking-mode flag, prompt, rubric,
scoring-policy, timestamp, run/config version, structured payload, and
application-normalized result. Schema validators reject secrets and private
reasoning fields. No canonical provider capture was fabricated during Phase 10.

## Evaluator, attribution, and reporting audit

- Outcome checks application-owned structured results and product-band
  authority without changing production scoring.
- Trajectory consumes existing structured `AgentTurnResponse` and bounds; it
  has no chain-of-thought dependency.
- Knowledge grounding resolves Phase 9 IDs, sources, claims, citations, and
  locators and fails closed on unknown provenance.
- Authority treats unsafe success, wrong ownership, and evidence gaps as
  failures or blocks; VETO findings cannot be averaged away.
- Lifecycle checks the frozen purpose-specific chronology:
  `WritingAttempt.created_at ASC, id ASC` for State,
  `LearningUpdate.created_at DESC, id DESC` for Memory, and
  `LearningUpdate.id DESC` for current Agent/guidance observation.
- Attribution selects the earliest evidence-backed failure boundary. Case
  invalidity and infrastructure blocks take precedence over asserted success.
- Calibration computes system-reference and human-human evidence separately,
  preserves raw/adjudicated references, and never classifies provider variance
  alone as deterministic regression.
- Machine and human reports share `StructuredEvalReport` as their sole truth
  model and retain versions, status counts, VETO count, first failure,
  provider/capture provenance, calibration evidence, exclusions, and limits.
- Reporting and evaluators require no free-form scratchpad or hidden reasoning.

The two interpretation rules remain enforced:

```text
provider variance != code regression
contract correctness != reference-score agreement
```

## Runner, promotion, and CI audit

The runner implements three separate modes. Deterministic Regression requires
explicit case executors, runs every applicable evaluator for a selected case,
is bounded and ordered, and reports missing/failed execution without corrupting
later cases. Live Calibration requires an explicitly injected provider
executor. Calibration Replay consumes immutable captures and performs no fresh
provider request.

Regression promotion is review-only. Calibration disagreement is rejected as a
promotion basis. A case cannot be promoted without provenance, frozen contract
basis, explicit approval, reproducibility, before-fix failure, after-fix pass,
and any required versioned fixture. Acceptance returns a decision for a manual,
reviewable corpus edit; it performs no automatic mutation.

The CI gate command is:

```bash
python -m app.eval.gate
```

It requires `IELTS_TEST_DATABASE_URL`, removes an inherited provider key, and
runs only the bounded deterministic suite. GitHub Actions supplies PostgreSQL
17 and executes this command before the complete backend suite. Live
Calibration is not a CI gate and no provider secret is configured for it.

## P10-16 validation evidence

All numbers below are actual results from the 2026-08-28 validation run:

| Validation | Result |
| --- | --- |
| CI-equivalent deterministic Eval gate | `71 passed`, zero skipped, 0.79 s |
| Complete backend suite | `1121 passed`, zero skipped, 33.68 s |
| Backend warnings | one Starlette/httpx dependency deprecation warning |
| Alembic | upgrade to `0006_submission_claim_recovery`; current check; downgrade to base; re-upgrade to head — all successful |
| FastAPI import | `IELTS Learning Agent`, 10 top-level route objects — successful |
| Web dependency install | successful; 0 reported vulnerabilities |
| ESLint | successful |
| TypeScript typecheck | successful |
| Web unit tests | `15 passed` |
| Next.js production build | successful; 9 routes generated/classified |
| Playwright E2E | `6 passed`, 22.2 s |
| Calibration Replay | `blocked`; zero cases; `insufficient_reference_data`; no provider call |

The backend and browser suites used disposable local PostgreSQL databases.
Alembic downgrade/upgrade ran only against a dedicated temporary migration
database. The temporary data had no production or personal records.

## Final scope audit

The `master...HEAD` changed-file audit found no change to dependency manifests,
Alembic files, public API routes, production services, existing scoring,
Planner, Memory, Agent, learner-state, evaluator, or public schema modules.
Runtime code additions are confined to the internal `app/eval/` package, which
is not imported by application runtime modules.

Phase 10 did not introduce:

- `writing-task2-v2` or any new score/rubric/product-band semantics;
- a new Planner strategy, Memory semantic change, or Agent authority expansion;
- a public Eval endpoint, dashboard, production trace table, or persistence
  migration;
- a dependency or provider abstraction;
- vector storage, embeddings, generic RAG, LangChain, LangGraph, Redis, Celery,
  Kafka, multi-agent behavior, fine-tuning, or runtime web search;
- Reading, Listening, Speaking, authentication, payments, P10-19, or Phase 11
  work;
- a private chain-of-thought requirement, secret, personal production record,
  or uncontrolled runtime network dependency.

No PR was opened and nothing was merged.

## Known limitations

1. The canonical calibration corpus has no admissible reference cases or raw
   ratings. Calibration correctness mechanics are implemented and tested with
   synthetic unit-test data, but the project has no examiner-grade calibration
   sample and makes no accuracy, bias, or provider-quality claim.
2. No canonical live provider capture exists. Replay currently demonstrates
   the truthful fail-closed zero-reference path, not empirical provider
   stability.
3. The local P10-16 run used PostgreSQL 18; CI is configured for the repository
   standard PostgreSQL 17 service. Actual remote CI status is separate from
   this local internal audit.
4. The backend suite reports one dependency deprecation warning; it is
   non-failing and unrelated to Phase 10 semantics.

These limitations do not justify fabricated evidence or weakening a
deterministic contract. Adding admissible references or captures requires the
operator workflow, source rights, provenance, review, and append-only evidence
rules.

## Stop gate

Batch B implementation and internal audit are complete. The next authority is
an external Phase 10 implementation review. Until that review returns an
approved outcome and the user separately authorizes repository workflow steps:

- do not mark Phase 10 COMPLETE;
- do not mark External Implementation Review APPROVED;
- do not open or merge a PR;
- do not modify `master`;
- do not start Phase 11.
