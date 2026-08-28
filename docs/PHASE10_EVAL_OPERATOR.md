# Phase 10 Eval Operator Workflow

**Policy:** `writing-eval-calibration-v1`
**Audience:** repository developers and reviewers
**Scope:** internal Writing Task 2 evaluation evidence only

This workflow operates the internal `app/eval/` package. It does not expose a
public Eval API, change `writing-task2-v1` scoring, or grant authority over
Learner State, Memory, Planner, Knowledge, Practice, or Agent behavior.

## 1. Execution modes

| Mode | Purpose | Provider/network | May gate CI |
| --- | --- | --- | --- |
| Deterministic Regression | Verify frozen application contracts and lifecycle behavior | None; frozen fixtures/captures only | Yes |
| Live Calibration | Observe a fresh provider result against admissible scoring references | Required | No |
| Calibration Replay | Recompute analysis from an immutable provider capture | None | No |

Keep these interpretations separate:

```text
provider variance != code regression
contract correctness != reference-score agreement
```

A deterministic failure remains a failure even when a score happens to agree
with a reference. A live score disagreement is calibration evidence, not by
itself a code regression.

## 2. Local deterministic gate

The gate refuses to run without `IELTS_TEST_DATABASE_URL`. The database must be
isolated, disposable, PostgreSQL-backed, and named with a separate `test`
token. Never point it at development, shared, or production-like data.

Using the repository Docker test profile:

```bash
docker compose --profile test up -d --wait test-db
```

Set the URL supplied by that profile, then run:

```bash
python -m app.eval.gate
```

The entrypoint removes any inherited `IELTS_DEEPSEEK_API_KEY`, runs the bounded
Eval framework self-tests, and then executes the actual canonical path:

```text
writing-eval-regression-corpus-v1
→ exact official executor registry
→ real deterministic Phase 1–9 services
→ applicable Eval evaluators
→ EvalRunner / RunnerSuiteResult
→ structured report / Markdown report
→ gate exit
```

The current canonical corpus contains 11 cases. Missing, unknown, or duplicate
executor registrations fail closed. Database-backed cases are reset before and
after execution in the validated disposable PostgreSQL database. Only suite
`pass` returns exit code 0; `fail`, `blocked`, and `invalid_case` return nonzero.

For the narrower canonical execution and report without framework self-tests:

```bash
python -m app.eval.regression_runtime
```

Run the complete backend suite separately when performing a full regression:

```bash
python -m pytest -q --strict-markers
```

## 3. Status, severity, and attribution

Statuses mean:

- `pass`: every applicable frozen assertion passed;
- `fail`: an applicable assertion failed;
- `not_applicable`: the valid case does not apply to the evaluator;
- `blocked`: trustworthy execution could not proceed;
- `invalid_case`: the case is malformed, incomplete, unsupported, or unsafe.

Severity is ordered `veto`, `major`, `minor`, then `info`. A `veto` is never
averaged away by passing checks. Examples include fabricated success,
score/learner authority bypass, wrong ownership, unknown provenance presented
as grounded, deterministic replay violation, unsafe database targeting, and a
malformed case reported as passing.

Attribution selects the first meaningful failing boundary in the frozen order,
from `case_validation` through `infrastructure`. Later symptoms cannot replace
an earlier cause. Review `first_failing_boundary` and `failure_codes` before
debugging downstream findings.

## 4. Calibration references

Calibration references belong only in
`tests/fixtures/eval/calibration_corpus.json`. Admit a case only after review
confirms all of the following:

- the question and essay may be stored and used under their source terms;
- provenance includes a stable source and locator;
- each raw rating has a distinct rater or pseudonymous rater ID, four criterion
  bands, and its own provenance;
- evidence tier `a`, `b`, or `c` is justified;
- ambiguity is recorded rather than silently resolved;
- adjudication, when present, is separate from immutable raw labels;
- missing evidence is not inferred and human disagreement is retained.

Tier C model-assisted evidence is exploratory and is never examiner truth.
Reference labels are append-only evidence and never become deterministic
production expected outputs.

Current limitation: the canonical calibration corpus has no fabricated
admissible reference labels. Its declared state is
`no_admissible_reference_data`, with zero cases. Therefore current live and
replay calibration correctly fail closed as `blocked` with
`insufficient_reference_data`; the repository makes no examiner-grade or
provider-quality claim.

## 5. Provider captures and replay

A Live Calibration caller must explicitly inject the reviewed provider
executor into `EvalRunner.run_live_calibration`. There is intentionally no
default provider and no live-calibration CI command. The runner records the
provider, model, thinking mode, prompt, rubric, scoring-policy, capture time,
and run/config versions with the application-normalized result.

Before committing a capture, validate it as `ProviderCapture` and review it for
licensing, personal data, and secrets. Never store API keys, credentials,
database URLs, private chain-of-thought, hidden reasoning, or unstructured
provider scratchpads. Captures are immutable and append-only. Store only
reviewable JSON fixture data and reference the stable `capture_id` from the
calibration case.

Replay uses no provider call:

```python
import json
from pathlib import Path

from app.eval.corpora import load_calibration_corpus
from app.eval.runner import EvalRunner
from app.eval.schemas import ProviderCapture

corpus = load_calibration_corpus(
    Path("tests/fixtures/eval/calibration_corpus.json")
)
captures = tuple(
    ProviderCapture.model_validate(item)
    for item in json.loads(Path("reviewed-provider-captures.json").read_text())
)
suite = EvalRunner().run_calibration_replay(
    run_id="reviewed-replay-id",
    corpus=corpus,
    captures=captures,
)
```

The example capture path is operator-supplied evidence, not a canonical file
that currently exists in this repository. If the corpus has no admissible
cases, replay must remain blocked and must not invent metrics.

## 6. Machine and human reports

Both report forms derive from the same `RunnerSuiteResult`; the Markdown report
must never become a second source of truth:

```python
from pathlib import Path

from app.eval.reporting import build_structured_report, render_human_report

report = build_structured_report(
    suite,
    config_version="reviewed-run-config-v1",
)
Path("eval-report.json").write_text(
    report.model_dump_json(indent=2), encoding="utf-8"
)
Path("eval-report.md").write_text(
    render_human_report(report), encoding="utf-8"
)
```

Treat generated reports as review artifacts. Before storing or sharing them,
check that inputs contain no essay text, secret, database URL, personal data,
or private reasoning. Reports must retain mode, frozen versions, status counts,
VETO count, first-failure distribution, provider/capture metadata where
applicable, calibration metrics, exclusions, and sample-size limitations.

## 7. Regression-case promotion

Do not edit the canonical regression corpus merely because a failure occurred.
Promotion is a deliberate review process:

1. reproduce and understand the historical failure;
2. identify the frozen application contract and first failure boundary;
3. create stable deterministic input and expected structured evidence;
4. use a frozen, versioned fixture/capture for provider-dependent behavior;
5. prove the before-fix failure and after-fix pass;
6. create `RegressionPromotionProposal` with provenance and an explicit review
   status;
7. run `evaluate_promotion` against canonical IDs and fixture paths;
8. only after an accepted decision, manually update the corpus in a separately
   reviewable commit and rerun the deterministic gate.

`evaluate_promotion` never writes the corpus. Calibration disagreement cannot
be a deterministic promotion basis. Do not special-case production behavior by
case ID, weaken an expectation to match an implementation, or delete a
regression without contract-change evidence and rationale.

## 8. CI behavior and limits

`.github/workflows/ci.yml` runs `python -m app.eval.gate` against its isolated
PostgreSQL 17 service before the complete backend and web suites. A nonzero gate
exit fails CI. Pull requests and the Phase 10 branch receive this gate.

CI intentionally does not:

- call a live provider or require a provider key;
- run Live Calibration as a merge gate;
- claim that replay is a fresh provider run;
- measure examiner-grade scoring accuracy without admissible references;
- judge generated-practice pedagogical quality;
- inspect private chain-of-thought;
- persist Eval traces or expose an Eval product/API.

For a release or external implementation review, retain the exact deterministic
gate, full backend, migration, frontend, build, browser, and replay outcomes in
the Phase 10 audit. Do not convert a blocked calibration run into a pass.
