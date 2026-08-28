# Phase 10 — Writing Evaluation Calibration v1

## Document status

**EXTERNAL IMPLEMENTATION REVIEW APPROVED — P10-12 and P10-15 are COMPLETE, P10-18 is INTERNAL_AUDIT_COMPLETE, the Phase 10 PR is READY_TO_OPEN, and Phase 10 is AWAITING_PR_VALIDATION.**

Phase 9 is COMPLETE and merged to `master` through PR #13 (merge commit
`75a667ff4ce16b79e7d4ba517081e1bd3d96fd57`). Phase 10 starts from the
post-merge documentation-sync commit
`1038af81f87ad1543e65c6093a10448c973193a8` on
`phase/10-writing-evaluation-calibration-v1`.

The Phase 10 Graph Review authorizes the Phase 10 design sequence through
P10-01 and P10-02. No Phase 10 implementation node may start before P10-01 and
P10-02 are COMPLETE and the formal Phase 10 External Design Review explicitly
approves the frozen contract. Graph Review approval authorizes P10-01; formal
External Design Review approval authorizes P10-03.

- Repository: `bluesblue320-hue/ielts-learning-agent`
- Branch: `phase/10-writing-evaluation-calibration-v1`
- Phase 9 master merge commit: `75a667ff4ce16b79e7d4ba517081e1bd3d96fd57`
- Phase 10 design base: `1038af81f87ad1543e65c6093a10448c973193a8`
- Scope: IELTS Writing Task 2 only
- Primary goal: trustworthy evaluation, calibration, regression detection, and failure attribution for the existing Writing learning lifecycle and bounded Writing Agent
- Runtime behavior default: frozen; evaluation is observational unless a later phase explicitly authorizes behavior changes
- Current evaluator semantics: `writing-task2-v1` remains frozen
- Phase 9 Knowledge: `ielts-writing-knowledge-v1` remains frozen
- Phase 10 status: AWAITING_PR_VALIDATION
- P10-00: COMPLETE
- Phase 10 Graph Review: APPROVED
- P10-01: COMPLETE
- P10-01 External Review: APPROVED
- P10-02: COMPLETE
- Phase 10 External Design Review: APPROVED
- P10-03: COMPLETE
- P10-04: COMPLETE
- P10-05: COMPLETE
- P10-06: COMPLETE
- P10-07: COMPLETE
- P10-08: COMPLETE
- P10-09: COMPLETE
- Phase 10 Milestone Review: APPROVED
- P10-10: COMPLETE
- P10-11: COMPLETE
- P10-12: COMPLETE
- P10-13: COMPLETE
- P10-14: COMPLETE
- P10-15: COMPLETE
- P10-16: COMPLETE
- P10-17: COMPLETE
- P10-18: INTERNAL_AUDIT_COMPLETE
- Batch B: COMPLETE
- Phase 10 implementation: INTERNAL_AUDIT_COMPLETE
- Phase 10 External Implementation Review: APPROVED
- Phase 10 PR: READY_TO_OPEN

## Phase goal

Build a deterministic contract-regression harness with separate live and replayable
score-calibration modes for the existing Writing Task 2 learning system so that
the repository can answer, with evidence:

1. whether final outcomes are correct against frozen contracts;
2. whether the Agent followed an allowed execution trajectory;
3. whether grounded guidance and generated practice preserve Knowledge provenance and authority boundaries;
4. whether the complete learning lifecycle remains internally consistent;
5. where a failure first occurred;
6. whether a change introduced a regression;
7. how closely system scoring aligns with an explicitly curated calibration reference set without silently changing `writing-task2-v1`.

Phase 10 is an evaluation phase, not a scoring-rewrite phase.

```text
Existing Writing system
  -> execute canonical eval case
  -> capture outputs + trace + persisted evidence
  -> deterministic evaluators
  -> structured verdicts
  -> failure attribution
  -> calibration / regression report
```

The central rule is:

```text
Eval may measure existing behavior.
Eval may expose a mismatch.
Eval may fail a regression.
Eval may NOT silently redefine production semantics to make the mismatch vanish.
```

## Execution modes and provider boundary

`WritingEvaluationService` calls an injected `LLMProvider` and normalizes its
validated structured output. Real Writing scores are therefore provider-backed,
not inherently deterministic. Phase 10 keeps the following modes separate:

1. **Deterministic Regression Mode** uses frozen mock or captured provider
   fixtures to run contract, lifecycle, authority, grounding, and deterministic
   replay checks. It is provider-free at execution time and is eligible for CI
   merge gating.
2. **Live Calibration Mode** invokes a real provider for real or canonical
   essays, compares the resulting scores with admissible reference labels, and
   measures agreement, bias, and variance. It is observational, non-
   deterministic, and never a required deterministic CI merge gate.
3. **Calibration Replay Mode** consumes previously captured provider outputs to
   recompute calibration metrics and regenerate reports without another provider
   invocation. It is reproducible analysis, not a substitute for a live score.

```text
provider variance != code regression
```

A different live provider score must not automatically fail deterministic CI.
Live provider failure or score disagreement is recorded as operational or
calibration evidence, not automatically as a deterministic contract failure.

## Why Phase 10 exists

Phases 2–9 established a functioning Writing learning loop:

```text
Writing submission
  -> evaluation
  -> accepted LearningUpdate
  -> learner-state projection
  -> Learning Memory
  -> deterministic Planner
  -> PracticeRecommendation
  -> Knowledge-grounded practice / guidance
  -> bounded Writing Agent
```

Existing tests protect many local contracts, but local tests alone do not prove that representative end-to-end Agent behavior remains correct across releases. Phase 10 therefore creates a reusable evaluation layer above the implemented system instead of adding another user-facing feature.

## Frozen authority model

Phase 10 must preserve the authority boundaries established by earlier phases.

```text
writing-task2-v1 evaluator
  -> owns existing score semantics

accepted LearningUpdate chronology
  -> owns authoritative persisted learning event order

Learner State / Memory projections
  -> describe the learner from durable accepted history

Planner
  -> owns WHAT should be trained next

ielts-writing-knowledge-v1
  -> owns source-backed IELTS explanatory / grounding content

Practice generator
  -> owns HOW an already-authorized recommendation is expressed as practice

Core Learning Agent
  -> orchestrates only within its existing bounded authority

Phase 10 Eval Harness
  -> observes, verifies, compares, attributes, and reports
  -> does not acquire production authority
```

## Explicit non-goals

Phase 10 must NOT introduce or authorize:

- Writing Task 1;
- Speaking, Reading, or Listening workflows;
- `writing-task2-v2`;
- changes to historical `writing-task2-v1` scoring behavior;
- automatic rubric repair based on calibration results;
- fine-tuning, SFT, LoRA, preference optimization, or model training;
- embeddings or vector databases;
- generic RAG frameworks;
- runtime web search or crawling;
- multi-agent orchestration;
- autonomous self-modification;
- a production LLM judge as the sole correctness authority;
- a new Planner strategy merely to improve eval pass rate;
- a new Memory semantic merely to improve eval pass rate;
- new public product APIs;
- user-facing Eval endpoints, Eval dashboards, or product features;
- public Eval endpoints or admin APIs such as `GET /eval`, `POST /eval`, or an `/eval` dashboard;
- evaluation data containing secrets, private user data, or uncontrolled production records;
- test assertions that bless current behavior solely because it currently exists.

Evaluation evidence may be exposed only through repository-native or internal
mechanisms: CLI, pytest, structured JSON/report artifacts, CI output, docs,
test-only instrumentation, or non-semantic internal application-owned evidence.
Any additional observability is limited to test-only instrumentation or
non-semantic internal evidence exposure, subject to P10-02. It must not change
production application behavior.

If evaluation identifies a material product-semantic problem, record and route the finding. Do not repair the production contract inside Phase 10 unless the frozen Phase 10 design explicitly includes a narrow defect fix required to make an earlier contract internally consistent.

## Evaluation architecture

```text
Canonical Eval Case
        |
        v
Isolated Eval Runner
        |
        +-------------------------------+
        |                               |
        v                               v
Production-compatible path         Captured evidence
(API/service/runtime)              outputs / trace / DB
        |                               |
        +---------------+---------------+
                        v
                 Evaluator Set
      +-----------------+------------------+
      |                 |                  |
      v                 v                  v
Outcome Eval      Trajectory Eval    Grounding Eval
      |                 |                  |
      +-----------------+------------------+
                        |
      +-----------------+------------------+
      |                                    |
      v                                    v
Authority Eval                    Lifecycle Eval
      |                                    |
      +-----------------+------------------+
                        v
                 Structured Verdict
                        |
                        v
                Failure Attribution
                        |
             +----------+-----------+
             |                      |
             v                      v
       Regression Report      Calibration Report
             |                      |
             +----------+-----------+
                        v
                Human-reviewable evidence
```

## Evaluator hierarchy

Phase 10 must distinguish evaluation dimensions instead of reducing everything to one blended score.

### 1. Outcome evaluation

Checks whether the final externally visible or persisted result satisfies the frozen contract for the case.

Examples:

- expected HTTP success/failure class;
- accepted versus rejected evaluation state;
- score field shape and allowed values;
- recommendation target consistency;
- grounded guidance structure;
- generated-practice ownership;
- final Agent response claims consistent with authoritative state.

### 2. Trajectory evaluation

Checks whether the system reached the result through an allowed sequence of steps.

Examples:

- no skipped required lifecycle transition;
- no forbidden direct state mutation;
- no generation before an owned recommendation exists;
- no Agent bypass around evaluator / Planner authority;
- bounded tool or service sequence where trace evidence exists;
- fail-closed handling of malformed provider output.

Trajectory assertions must target externally observable or application-owned trace/state evidence. They must not require private model chain-of-thought.

### 3. Knowledge grounding evaluation

Checks that claims governed by Phase 9 Knowledge remain grounded in stable Knowledge IDs and source locators.

Examples:

- all returned Knowledge IDs resolve;
- citations are application-assembled;
- no unknown provenance reference;
- practice Knowledge context matches the selected recommendation;
- guidance does not invent an unsupported IELTS rule;
- identical normalized deterministic retrieval input produces the same ordered Knowledge IDs.

### 4. Authority / safety evaluation

Checks that subsystem ownership remains intact.

Examples:

- model output cannot redefine score authority;
- Knowledge cannot override Planner target skill / target band;
- Agent cannot invent learner progress;
- provider failure cannot be converted into a fabricated success;
- stale or mismatched chronology cannot be combined into one authoritative response;
- malformed IDs or state references fail closed.

### 5. Learning-lifecycle evaluation

Checks cross-layer consistency across one or more accepted learner episodes.

Examples:

- evaluation result and LearningUpdate agree;
- state projection follows accepted durable history;
- Memory uses the same chronology;
- Planner consumes the authoritative current projection;
- recommendation ownership is preserved;
- generated practice corresponds to the recommendation that owns it;
- subsequent evaluation can be replayed without corrupting earlier evidence.

### 6. Score calibration analysis

Compares existing `writing-task2-v1` outputs against a curated reference set. Calibration is evidence, not automatic truth rewriting.

Phase 10 must distinguish:

```text
contract correctness
!=
reference-score agreement
```

A case may be contract-correct yet disagree with an external calibration reference. Such disagreement must be reported rather than silently changing the rubric.

## Result philosophy

No single average score may hide a veto-class failure.

At minimum, the frozen contract must support separate concepts equivalent to:

```text
PASS
FAIL
NOT_APPLICABLE
BLOCKED / INVALID_CASE
```

and severity classes equivalent to:

```text
VETO
MAJOR
MINOR
INFO
```

Exact schema names are frozen by P10-02, not by this design graph.

Examples of likely VETO failures:

- fabricated success when an authoritative operation failed;
- score or learner-state authority bypass;
- unknown or invented Knowledge provenance presented as grounded;
- lifecycle evidence attached to the wrong learner / episode / recommendation;
- non-deterministic replay where the frozen path is required to be deterministic;
- eval runner mutating non-isolated or production-like data.

## Corpus principles

Phase 10 maintains two repository-safe, reviewable, bounded, and versioned
corpora. P10-02 freezes their exact identifiers and formats; suggested concepts
are `writing-eval-regression-corpus-v1` and
`writing-score-calibration-corpus-v1`.

### Deterministic regression corpus

This corpus contains deterministic contract cases, lifecycle cases, authority
and grounding cases, provider validation/failure fixtures, structured Agent
trajectory cases, and historical regression cases. Expected outputs are
application-contract expectations backed by frozen mock or captured provider
fixtures. It covers, where relevant, accepted evaluations, half-band state,
Memory, Planner ties, recommendation ownership, Knowledge provenance,
generation compatibility, chronology/freshness mismatches, and multi-episode
trajectories. It has no runtime network dependency and may be CI-gating.

### Score calibration corpus

This corpus contains essay/input material, reference criterion and overall
scores where admissible, rater provenance, evidence tier, ambiguity metadata,
and adjudication metadata. It is for live calibration measurement and captured-
output replay analysis. Reference human or calibration labels must never
silently become deterministic production expected outputs.

Neither corpus may copy large copyrighted source passages, contain secrets, or
use uncontrolled production records.

## Calibration reference principles

P10-02 must freeze what qualifies as calibration evidence.

At minimum:

- every reference label must identify its origin;
- machine-generated reference labels cannot be presented as official examiner truth;
- human labels must record enough metadata to distinguish single-rater opinion from stronger adjudicated evidence;
- when two or more independent human labels exist, raw rater labels must be
  preserved and any adjudicated label stored separately;
- public or licensed sample use must respect source constraints;
- reference labels and production rubric outputs must be stored as separate fields;
- no disagreement may be erased by overwriting the reference or production result in place;
- ambiguous cases must remain explicitly ambiguous.

Potential reference tiers may include:

```text
Tier A: authoritative / officially published scoring evidence where usable
Tier B: independently human-reviewed or adjudicated calibration evidence
Tier C: exploratory model-assisted labels, never correctness authority
```

The exact tiers and admissibility rules are frozen in P10-02.

## Determinism and provider policy

Deterministic Regression Mode is the provider-free CI-gating path. It verifies
structured contracts using frozen mock or captured outputs; it does not claim
that a live Writing score is deterministic. Live Calibration Mode and Calibration
Replay Mode remain separately reported, and neither may convert provider variance
into a code-regression verdict.

```text
Structured contract
  -> deterministic verifier

Subjective language-quality dimension not derivable from structure
  -> optional secondary evaluator only if explicitly approved
```

If an LLM judge is introduced at all in Phase 10:

- it must be versioned;
- its prompt and model configuration must be recorded;
- it must never be the sole authority for veto-class correctness;
- deterministic contract checks take precedence;
- judge unavailability must not fabricate PASS;
- nondeterministic results must be reported as such;
- provider-backed evaluation must be separable from deterministic regression
  gating and calibration replay.

## Dependency graph

```text
START
  -> P10-00 Phase 10 Kickoff / Graph Establishment [COMPLETE]
  -> Phase 10 Graph Review [APPROVED]
  -> P10-01 Existing Evaluation Surface Audit [COMPLETE]
  -> P10-01 External Review [APPROVED]
  -> P10-02 Evaluation & Calibration Contract Freeze [COMPLETE]
  -> Phase 10 External Design Review [APPROVED]
  -> P10-03 Canonical Eval Case Schemas [COMPLETE]
  -> P10-04 Regression and Calibration Corpora v1 [COMPLETE]
  -> P10-05 Deterministic Outcome Evaluator [COMPLETE]
  -> P10-06 Trajectory Evaluator [COMPLETE]
  -> P10-07 Knowledge Grounding Evaluator [COMPLETE]
  -> P10-08 Authority / Fail-Closed Evaluator [COMPLETE]
  -> P10-09 Learning Lifecycle Evaluator [COMPLETE]
  -> Phase 10 Milestone Review [APPROVED]
  -> P10-10 Writing Score Calibration Analysis [COMPLETE]
  -> P10-11 Failure Taxonomy & Attribution [COMPLETE]
  -> P10-12 Eval Runner / Harness [COMPLETE]
  -> P10-13 Machine-Readable Eval Result & Human Report [COMPLETE]
  -> P10-14 Regression Corpus Promotion [COMPLETE]
  -> P10-15 CI-Compatible Deterministic Eval Gate [COMPLETE]
  -> P10-16 Full Phase 1-10 Regression Validation [COMPLETE]
  -> P10-17 Documentation / Operator Workflow [COMPLETE]
  -> P10-18 Internal Final Audit [INTERNAL_AUDIT_COMPLETE]
  -> External Implementation Review [APPROVED]
  -> PR / CI / merge authorization
  -> Phase 10 COMPLETE
  -> STOP (do not start Phase 11)
```

P10-02 freezes a non-linear dependency DAG and permits future serial batches,
but execution remains serial: at most one node may be ACTIVE at a time. Select
the lowest-numbered READY node unless the user explicitly selects another valid
READY node.

### Authorized future batch boundaries

After Formal Phase 10 External Design Review is APPROVED, Batch A is:

```text
P10-03 -> P10-04 -> P10-05 -> P10-06 -> P10-07 -> P10-08 -> P10-09
-> STOP -> Phase 10 Milestone Review [APPROVED]
```

Only after Phase 10 Milestone Review is APPROVED, Batch B is:

```text
P10-10 -> P10-11 -> P10-12 -> P10-13 -> P10-14 -> P10-15 -> P10-16
-> P10-17 -> P10-18 -> STOP -> External Implementation Review
```

These are future authorization boundaries only. They do not mark a downstream
node `READY`, authorize parallel work, or cross either review gate.

## P10-00 — Phase 10 Kickoff / Graph Establishment — COMPLETE

### Objective

Establish an explicit Phase 10 design boundary after Phase 9 merge without starting implementation.

### Evidence

- Phase 9 merged through PR #13.
- Phase 10 branch exists.
- post-merge status sync commit exists: `1038af81f87ad1543e65c6093a10448c973193a8`.
- this Phase 10 graph exists.

### Acceptance

P10-01 may be selected as the first executable design node. No implementation node is authorized.

## P10-01 — Existing Evaluation Surface Audit — COMPLETE

### External Review

APPROVED.

### Objective

Audit the repository's actual evaluation, testing, tracing, fixtures, scoring, lifecycle, Agent, Knowledge, and CI surfaces before freezing any Phase 10 contract.

### Required inspection

At minimum inspect:

- `writing-task2-v1` evaluator implementation and tests;
- provider validation / fallback paths;
- LearningUpdate persistence and chronology;
- learner-state projection;
- Memory read models;
- Planner v1/v2 compatibility and tie logic;
- practice generation v1/v2 ownership;
- Phase 9 Knowledge retrieval / compatibility / guidance / citation paths;
- bounded Writing Agent runtime and its tests;
- API and browser lifecycle tests;
- existing fixtures and test factories;
- CI workflow(s), test commands, database assumptions, and provider-free paths;
- existing audit documents for Phases 2–9;
- any current regression fixtures or historical bug tests.

### Deliverable

Create a repository-backed audit document, expected as:

```text
docs/PHASE10_EVAL_AUDIT.md
```

The audit must separate:

```text
already covered deterministically
partially covered
not covered
too subjective for deterministic verification
requires calibration reference data
requires trace / evidence exposure
out of scope
```

### Required questions

The audit must answer at least:

1. What correctness properties are already enforced by local unit/API tests?
2. Which important cross-layer invariants lack end-to-end evaluation?
3. What execution trace or persistence evidence is already observable without production changes?
4. Where would an Eval Harness need new test-only instrumentation, if anywhere?
5. Which provider-dependent paths have deterministic fallbacks or mocks?
6. Which current tests accidentally assert implementation detail rather than a stable contract?
7. What historical failures should become regression cases?
8. What score-calibration evidence already exists, if any?
9. Which CI environment can run the deterministic core eval suite?
10. What is the smallest viable v1 evaluation surface?

### Forbidden during P10-01

- implementing the Eval Harness;
- changing scoring semantics;
- changing Planner / Memory / Agent behavior;
- adding dependencies;
- adding production APIs;
- curating final golden labels before admissibility rules are frozen;
- declaring a preferred framework before the audit demonstrates a need.

### Acceptance criteria

- audit references actual files/tests/commands;
- coverage gaps are explicit;
- deterministic versus subjective evaluation boundaries are explicit;
- required evidence surfaces are identified;
- no production behavior is changed;
- P10-02 has enough evidence to freeze a minimal contract.

## P10-02 — Evaluation & Calibration Contract Freeze — COMPLETE

### Dependency

P10-01 COMPLETE.

### Objective

Freeze the normative Phase 10 policy before implementation.

### Expected deliverable

Create:

```text
docs/WRITING_EVAL_CALIBRATION_POLICY.md
```

### Contract must freeze

At minimum:

1. Phase 10 scope and non-goals.
2. Eval case version and identity rules.
3. Eval result version and status vocabulary.
4. Evaluator IDs / dimensions.
5. severity and veto semantics.
6. Deterministic Regression, Live Calibration, and Calibration Replay mode rules.
7. trace/evidence representation.
8. isolation and database lifecycle.
9. distinct regression-corpus and calibration-corpus storage formats and
   authority boundaries.
10. reference-label admissibility, provenance, and inter-rater metadata.
11. calibration metrics, uncertainty, and interpretation.
12. regression promotion rules.
13. fail-closed behavior.
14. CI gating policy, limited to deterministic regression checks.
15. compatibility rules for historical production versions.
16. provider configuration and capture recording for live calibration or a
   secondary judge.
17. exact prohibition on private chain-of-thought requirements.
18. update process for regression fixtures and calibration labels.
19. rules preventing test-data overfitting or silent semantic repair.
20. audit/report evidence required for Phase completion.

### Versioning

P10-02 freezes exact stable identifiers before implementation in
`docs/WRITING_EVAL_CALIBRATION_POLICY.md`, including:

```text
writing-eval-calibration-v1
writing-eval-regression-corpus-v1
writing-score-calibration-corpus-v1
writing-eval-regression-case-v1
writing-score-calibration-case-v1
writing-score-reference-label-v1
writing-score-provider-capture-v1
writing-eval-result-v1
writing-score-calibration-result-v1
writing-eval-failure-taxonomy-v1
writing-eval-report-v1
```

These names are frozen by `writing-eval-calibration-v1`; P10-03 must use them.

### Formal External Design Review gate

After P10-02:

```text
P10-01 audit
  + P10-02 frozen policy
  + PHASE10_GRAPH.md
  -> Formal Phase 10 External Design Review
```

If the formal review is not APPROVED, remain in DESIGN/FIXING. Do not begin
P10-03. After P10-02 completes, STOP for the formal review unless separate
authority already exists according to the repository workflow.

## P10-03 — Canonical Eval Case Schemas — COMPLETE

### Dependency

Formal Phase 10 External Design Review APPROVED.

### Objective

Implement strict versioned schemas for deterministic regression cases and their
contract expectations, separately from calibration cases, reference labels,
rater metadata, execution evidence, evaluator verdicts, failure attribution,
and suite results.

### Requirements

- closed enums where the frozen policy requires them;
- explicit version fields;
- stable case IDs in each corpus;
- no free-form executable code embedded in corpus rows;
- explicit expected authority/evidence references for regression expectations;
- calibration labels, raw-rater metadata, and adjudication metadata remain
  separate from deterministic expected outputs;
- strict validation of unknown evaluator IDs and malformed expectations;
- deterministic serialization suitable for repository review;
- no production database schema migration unless P10-02 demonstrates and explicitly authorizes a need.

### Tests

Prove malformed, duplicate, unsupported-version, unknown-evaluator, and ambiguous required-field cases fail closed.

## P10-04 — Regression and Calibration Corpora v1 — COMPLETE

### Objective

Create the bounded deterministic regression corpus and separately the score
calibration corpus using the P10-03 schemas and P10-02 admissibility rules.

### Regression corpus coverage

The deterministic regression corpus must cover representative success, boundary,
and failure cases across evaluator/provider validation contracts,
accepted/rejected lifecycle transitions, learner state, Memory, Planner ties,
recommendation ownership, Knowledge retrieval/guidance/provenance, generation
v1/v2 compatibility, structured Agent trajectories, malformed-provider paths,
chronology/freshness mismatches, and at least one multi-episode learner
trajectory.

### Calibration corpus coverage

The calibration corpus must preserve the essay/input, reference criterion and
overall score where admissible, evidence tier, raw rater labels, ambiguity, and
adjudication metadata. Its labels measure agreement; they are not deterministic
production expected outputs.

### Corpus rules

- every case has rationale;
- every deterministic expectation has a declared contract authority source;
- every calibration label has provenance metadata;
- ambiguous references remain explicitly ambiguous;
- deterministic regression cases have no network dependency;
- no hidden local files, secrets, or production-user records.

The final minimum case count for each corpus must be justified by coverage, not
by an arbitrary large number. P10-02 may freeze category minimums.

## P10-05 — Deterministic Outcome Evaluator — COMPLETE

### Objective

Evaluate final structured outputs and persisted outcomes against case expectations.

### Requirements

- deterministic;
- provider-free;
- exact structured assertions for contract-owned fields;
- useful mismatch diagnostics;
- supports veto failures;
- does not infer correctness from status code alone;
- separates "contract mismatch" from "calibration disagreement".

### Examples

- score object shape/value constraints;
- accepted update identity;
- current recommendation ownership;
- guidance response versions;
- `AgentTurnResponse` initial/final observations, `AgentStep` sequence,
  `stop_reason`, recommendation ownership, practice ownership, and freshness
  or chronology evidence.

Structured Agent response and state evidence is authoritative. Natural-language
claim checking is secondary and applies only where free-form output actually
exists; it is never the primary correctness authority.

## P10-06 — Trajectory Evaluator — COMPLETE

### Objective

Verify allowed lifecycle execution from observable application evidence.

### Requirements

- no private chain-of-thought;
- rely on tool/service traces, event IDs, persistence rows, version fields, or other application-owned evidence;
- detect missing, duplicated, reordered, stale, or forbidden transitions where the contract defines order;
- bounded and deterministic.

If required evidence is not observable, add the smallest test-only or non-semantic instrumentation approved by P10-02. Do not add a production behavioral dependency merely for eval convenience.

## P10-07 — Knowledge Grounding Evaluator — COMPLETE

### Objective

Verify Phase 9 grounding, citation, and provenance invariants under canonical cases.

### Requirements

- every referenced Knowledge ID resolves to the frozen snapshot;
- every source locator resolves according to Phase 9 policy;
- citations remain application-owned;
- expected deterministic retrieval order is reproducible;
- guidance / generation Knowledge context matches the correct learner chronology and recommendation;
- unsupported grounded claims fail rather than silently pass.

This evaluator must reuse Phase 9 authority definitions; it must not create a second Knowledge truth source.

## P10-08 — Authority / Fail-Closed Evaluator — COMPLETE

### Objective

Verify subsystem ownership and failure handling.

### Required coverage

At minimum include cases for:

- malformed provider response;
- unknown IDs / versions;
- stale or mismatched episode/recommendation evidence;
- generator attempting to contradict the recommendation;
- Knowledge attempting to override Planner authority;
- `AgentTurnResponse` or its structured evidence claiming an operation succeeded
  when the authoritative operation did not succeed;
- unsupported action or route;
- missing required evidence.

Veto-class authority violations must fail the suite regardless of lower-severity passes elsewhere.

## P10-09 — Learning Lifecycle Evaluator — COMPLETE

### Objective

Verify the closed-loop relationships built across Phases 2–9.

### Canonical chain

```text
submission/evaluation
  -> LearningUpdate
  -> state projection
  -> Memory
  -> Planner
  -> recommendation
  -> grounded practice/guidance
  -> later episode / re-evaluation
```

### Requirements

- evidence identity remains consistent end to end;
- chronology uses frozen ordering rules;
- historical versions remain replayable where earlier phases require them;
- learner isolation is preserved;
- repeated execution of deterministic read/eval paths does not mutate state;
- lifecycle evaluator reports the earliest failing boundary where evidence supports attribution.

## Phase 10 Milestone Review

### Dependency

`P10-09 = COMPLETE`.

### Status before review

`APPROVED`. P10-10 is `READY`, and Batch B is authorized for serial execution through P10-18.

### Review inputs and scope

Review P10-03 through P10-09 outputs for schema correctness; regression and
calibration corpus separation; deterministic and trajectory evaluator evidence;
Knowledge grounding; authority/fail-closed and lifecycle correctness;
frozen-contract preservation; production semantic drift; unauthorized
dependency, migration, or API changes; and relevant tests/evidence.

### Results and approval effect

Possible results are `APPROVED` and `FIXING_REQUIRED`.

`APPROVED` makes P10-10 `READY`. `FIXING_REQUIRED` keeps P10-10 blocked. P10-09
completion alone does not make P10-10 ready.

## P10-10 — Writing Score Calibration Analysis — COMPLETE

### Dependency

`P10-09 = COMPLETE` and `Phase 10 Milestone Review = APPROVED`.

The Milestone Review is APPROVED. P10-10 is `READY`; later Batch B nodes remain blocked until their predecessor completes.

### Objective

In Live Calibration Mode, measure agreement between frozen `writing-task2-v1`
outputs and admissible reference labels without redefining score semantics. In
Calibration Replay Mode, recompute the same analysis from captured provider
outputs without another provider invocation.

### Minimum analysis dimensions

Subject to P10-02 final freeze, include appropriate metrics such as:

- exact overall-band agreement;
- within-0.5 and within-1.0 agreement;
- per-criterion absolute error;
- signed bias by criterion;
- distribution of disagreements;
- disagreement by reference-evidence tier;
- explicit sample count and coverage caveats.

When two or more independent human labels exist, also report human uncertainty
without replacing raw labels: exact agreement, within-0.5 agreement, mean
absolute rater difference, and criterion-level disagreement where appropriate
and where sample size supports interpretation. Preserve any adjudicated label
separately from raw rater labels.

Do not present a metric as statistically meaningful when the dataset is too
small to support that claim. Do not conclude that the system is inaccurate when
substantial human disagreement exists without reporting that uncertainty.

### Calibration failure behavior

A material mismatch or live-provider operational failure must produce evidence
such as:

```text
case ID
reference provenance
raw and adjudicated labels where available
captured evaluator output
delta
criterion(s)
confidence / ambiguity metadata
provider execution metadata
```

It must not automatically mutate the rubric or a calibration label, and it must
not be treated as deterministic CI contract failure merely because a live score
differs.

## P10-11 — Failure Taxonomy & Attribution — COMPLETE

### Objective

Provide deterministic failure classification so regressions are actionable.

### Minimum failure families

Freeze exact IDs in P10-02, covering concepts such as:

```text
CASE_INVALID
EVALUATION_CONTRACT
PROVIDER_VALIDATION
PERSISTENCE
CHRONOLOGY
STATE_PROJECTION
MEMORY
PLANNER
RECOMMENDATION_OWNERSHIP
KNOWLEDGE_GROUNDING
GENERATION
AGENT_ROUTING
AGENT_AUTHORITY
API_CONTRACT
CALIBRATION_DISAGREEMENT
INFRASTRUCTURE
UNKNOWN
```

### Attribution rule

Prefer the earliest proven failing boundary. Do not claim root cause when only a symptom is observable; record `UNKNOWN` or an equivalent bounded status with supporting evidence.

## P10-12 — Eval Runner / Harness — COMPLETE

### Objective

Build one reproducible entrypoint that executes selected corpus cases in an
isolated environment and applies the registered evaluator set.

### Required characteristics

- Deterministic Regression Mode runs frozen mock/captured provider fixtures
  without external model/network access and has a non-zero exit only for gated
  deterministic contract failures;
- Live Calibration Mode is explicit, provider-backed, observational, and never
  a required deterministic CI merge gate;
- Calibration Replay Mode consumes captured provider outputs without another
  provider invocation to recompute metrics and reports;
- case selection/filtering by stable metadata and corpus identity;
- isolated database state;
- repeatable setup/teardown;
- bounded runtime and output;
- structured machine-readable result including execution mode;
- safe interruption without contaminating later cases;
- no mutation of production-like user data.

The harness may be CLI, pytest-integrated, or another minimal repository-native form. P10-01/P10-02 determine the simplest justified approach; do not add an Eval framework merely for branding.

External-review repair adds `app/eval/regression_runtime.py` as the official
provider-free path. It loads all 11 canonical cases, requires an exact executor
registry match, isolates every database case with a validated test PostgreSQL
reset, invokes real Phase 1–9 services and all applicable evaluators, and returns
`RunnerSuiteResult` without operator-supplied executors. The stale-practice
case now correctly uses Outcome plus Authority because the real Phase 8 stale
fence raises `AgentStalePracticeError` before an `AgentTurnResponse` exists.

## P10-13 — Machine-Readable Eval Result & Human Report — COMPLETE

### Objective

Produce durable evidence that is both automation-friendly and reviewable.

### Machine-readable output

Must include enough information to reproduce/inspect:

- execution mode and corpus identity/version;
- suite version;
- case IDs and case versions;
- evaluator IDs/versions;
- pass/fail/not-applicable verdicts;
- severity;
- failure attribution;
- relevant production version identifiers;
- calibration deltas and human-disagreement evidence where applicable;
- captured provider metadata allowed by policy;
- timestamps only where they do not break deterministic comparison semantics.

### Human report

Expected Phase artifact:

```text
docs/PHASE10_EVAL_REPORT.md
```

The report must be answer-first and include:

- deterministic regression corpus coverage and gated regression status;
- veto failures;
- major failures;
- separate live-calibration and calibration-replay findings;
- human-reference disagreement and adjudication caveats where applicable;
- known blind spots;
- provider-dependent exclusions or operational failures;
- recommended follow-up without silently implementing future-phase changes.

## P10-14 — Regression Corpus Promotion — COMPLETE

### Objective

Define and implement a controlled path for turning verified bugs into permanent canonical regression cases.

### Requirements

Every promoted case must have:

- stable ID;
- origin / bug reference;
- minimal reproduction;
- expected contract;
- failure family;
- rationale;
- proof the case fails before the repair when reproducibly available;
- proof it passes after the repair;
- no unrelated implementation detail encoded as the expectation.

Regression-corpus edits must be reviewable. Deleting or weakening a regression
case requires an explicit rationale and contract-change evidence. Calibration
labels remain separate measurement evidence and may not weaken a regression
expectation.

## P10-15 — CI-Compatible Deterministic Eval Gate — COMPLETE

### Objective

Add the deterministic core suite to CI at a cost and runtime appropriate for the repository.

### Requirements

- provider-free Deterministic Regression Mode as the only gated path;
- reproducible test/database setup;
- clear command documented locally and in CI;
- veto/major deterministic contract failures cause CI failure according to P10-02;
- Live Calibration Mode and Calibration Replay Mode report separately and must
  not masquerade as deterministic gates;
- existing Phase 1–9 test suite remains intact.

If CI runtime is too high, split smoke and full deterministic suites only if the policy defines exactly what remains merge-gating.

The repaired `python -m app.eval.gate` first runs bounded Eval framework
self-tests and then executes the official canonical runtime. Only suite `PASS`
returns zero; `FAIL`, `BLOCKED`, and `INVALID_CASE` return nonzero, while
registry, database-isolation, migration, or unexpected runtime failures return
an infrastructure error.

## P10-16 — Full Phase 1–10 Regression Validation — COMPLETE

### Objective

Run the complete relevant validation stack after Phase 10 integration.

### Required evidence

At minimum capture:

- backend tests;
- frontend/browser checks where existing repository contracts require them;
- database/migration checks even if no migration is expected, when repository standard validation includes them;
- Deterministic Regression Mode result;
- separate Live Calibration and/or Calibration Replay analysis result;
- CI-equivalent commands for the deterministic gate only;
- no unexpected production contract changes.

Historical Phase 1–9 behavior must remain compatible unless P10-02 explicitly freezes a justified narrow compatibility exception.

### P10-16 validation evidence

- CI-equivalent provider-free deterministic gate: `71 passed`, zero skipped;
- complete backend suite against isolated PostgreSQL: `1121 passed`, zero skipped,
  with one dependency deprecation warning;
- Alembic integrity: upgrade to `0006_submission_claim_recovery`, current-head
  check, downgrade to base, and re-upgrade to head all succeeded;
- FastAPI application import and route registration succeeded;
- web lint and TypeScript typecheck succeeded;
- web unit tests: `15 passed`; Next.js production build succeeded;
- Playwright browser regression: `6 passed`;
- Calibration Replay Mode: `BLOCKED` with
  `insufficient_reference_data`, because the canonical calibration corpus has
  zero admissible reference cases; no provider call or quality claim was made;
- no migration, production scoring change, or runtime application contract
  change was introduced by Batch B validation.

## P10-17 — Documentation / Operator Workflow — COMPLETE

### Objective

Make the Eval Harness usable by a future maintainer without tribal knowledge.

### Update as needed

- `README.md`;
- `AGENTS.md`;
- Phase 10 policy;
- eval dataset documentation;
- local execution command;
- adding/promoting a regression case;
- interpreting failure severity;
- interpreting calibration disagreement;
- provider-backed optional evaluation, if any;
- CI behavior.

Documentation must not overstate examiner validity, statistical confidence, or production capability.

The canonical operator workflow is docs/PHASE10_EVAL_OPERATOR.md.

## P10-18 — Internal Final Audit — INTERNAL_AUDIT_COMPLETE

### Objective

Verify that Phase 10 satisfies its frozen contract before external implementation review.

### Expected deliverable

```text
docs/PHASE10_AUDIT.md
```

### Audit must prove

1. every frozen P10-02 invariant is implemented or explicitly marked blocked;
2. deterministic regression and score calibration corpora each validate against
   their frozen schemas and remain authority-separated;
3. Deterministic Regression Mode and Calibration Replay Mode are reproducible;
4. veto-class violations fail closed;
5. failure attribution is evidence-backed;
6. Knowledge grounding reuses Phase 9 authority;
7. `writing-task2-v1` semantics were not silently changed;
8. Planner / Memory / Agent authority was not expanded;
9. calibration results preserve reference provenance, raw-rater disagreement,
   adjudication evidence where present, and captured-provider provenance;
10. CI gating includes only Deterministic Regression Mode as frozen by policy;
11. regression corpus is reviewable;
12. full relevant Phase 1–10 tests pass;
13. no secret, personal production data, or uncontrolled network dependency was introduced;
14. docs match implementation;
15. unresolved limitations are explicit.

### External-review repair re-audit evidence

- official runtime: `app/eval/regression_runtime.py`;
- canonical cases / executor coverage: `11 / 11`;
- actual suite result: `PASS` with 11 PASS, zero FAIL/BLOCKED/INVALID_CASE;
- deterministic Eval self-tests: `73 passed`;
- full backend: `1131 passed` with one dependency deprecation warning;
- web: lint, typecheck, 15 unit tests, and 9-route production build succeeded;
- browser: Playwright `6 passed`;
- Alembic: current head, downgrade to base, re-upgrade to head succeeded on
  disposable PostgreSQL 17;
- GitHub Actions run `33160887212` succeeded, including the canonical gate,
  backend, web quality gates, and Playwright;
- provider-free: no provider key and no live provider call;
- no migration, dependency, public Eval API, scoring/Planner/Memory/Agent
  semantic change, PR, or merge.

Current status after external approval:

```text
P10-18 = INTERNAL_AUDIT_COMPLETE
Phase 10 External Implementation Review = APPROVED
Phase 10 PR = READY_TO_OPEN
Phase 10 = AWAITING_PR_VALIDATION
```

This status is not authorization to merge.

## External Implementation Review gate — APPROVED

External Implementation Review must inspect at least:

- frozen P10-02 policy;
- canonical cases and provenance;
- deterministic evaluator correctness;
- fail-closed behavior;
- lifecycle and authority assertions;
- calibration methodology and claims;
- regression promotion rules;
- CI gate;
- Phase 10 audit evidence.

Possible outcomes:

```text
APPROVED
APPROVED_WITH_NON_BLOCKING_NOTES
FIXING_REQUIRED
BLOCKED
```

The recorded APPROVED outcome authorizes PR creation and PR CI validation according to the repository's normal process; it does not authorize merge.

## Phase completion criteria

Phase 10 is COMPLETE only when all of the following are true:

1. P10-01 through P10-18 are COMPLETE according to the frozen graph/policy.
2. Formal Phase 10 External Design Review is APPROVED.
3. External Implementation Review is APPROVED or the project's explicitly accepted equivalent approval state.
4. Deterministic Regression Mode passes its merge-gating suite.
5. separate live-calibration and/or calibration-replay reports exist with
   provenance, provider-variance, and human-disagreement caveats.
6. full relevant regression suite passes.
7. documentation is synchronized.
8. PR/CI/merge steps explicitly authorized by the user are complete.
9. the final merged state is verified on `master` when merge is authorized.

## Phase stop conditions

Immediately STOP and report instead of routing around the graph if:

- a material conflict requires changing frozen `writing-task2-v1` semantics;
- a proposed calibration label lacks admissible provenance but is required as correctness authority;
- a required deterministic evaluator can only be implemented by inspecting private chain-of-thought;
- evaluation would require unsafe access to production learner data;
- implementation would require a future-phase capability outside this graph;
- Formal Phase 10 External Design Review or External Implementation Review blocks progress;
- required validation cannot be made trustworthy;
- continuing would require unauthorized PR, merge, history rewrite, or secret handling.

## Phase 10 execution rule

Use [`DEVELOPMENT_LOOP.md`](DEVELOPMENT_LOOP.md) for every executable node.

At any time:

- at most one node is `ACTIVE`;
- execute the lowest-numbered `READY` node unless the user explicitly selects another valid `READY` node;
- do not route around failed dependencies;
- commit only the logical node after validation;
- record evidence before moving forward;
- do not start Phase 11 automatically.

Current authorized node after completed Batch A repairs:

```text
P10-03 Canonical Eval Case Schemas [COMPLETE]
```

Batch A authorizes only serial execution of P10-03 through P10-09. Do not begin
P10-10 before Phase 10 Milestone Review is explicitly APPROVED.
