# Phase 10 — Writing Evaluation Calibration v1

## Document status

**DESIGN GRAPH CREATED — P10-01 READY. IMPLEMENTATION NOT AUTHORIZED.**

Phase 9 is COMPLETE and merged to `master` through PR #13 (merge commit
`75a667ff4ce16b79e7d4ba517081e1bd3d96fd57`). Phase 10 starts from the
post-merge documentation-sync commit
`1038af81f87ad1543e65c6093a10448c973193a8` on
`phase/10-writing-evaluation-calibration-v1`.

This graph authorizes only the Phase 10 design sequence until External Design
Review is APPROVED. No Phase 10 implementation node may start before P10-01 and
P10-02 are COMPLETE and External Design Review explicitly approves the frozen
contract.

- Repository: `bluesblue320-hue/ielts-learning-agent`
- Branch: `phase/10-writing-evaluation-calibration-v1`
- Phase 9 master merge commit: `75a667ff4ce16b79e7d4ba517081e1bd3d96fd57`
- Phase 10 design base: `1038af81f87ad1543e65c6093a10448c973193a8`
- Scope: IELTS Writing Task 2 only
- Primary goal: trustworthy evaluation, calibration, regression detection, and failure attribution for the existing Writing learning lifecycle and bounded Writing Agent
- Runtime behavior default: frozen; evaluation is observational unless a later phase explicitly authorizes behavior changes
- Current evaluator semantics: `writing-task2-v1` remains frozen
- Phase 9 Knowledge: `ielts-writing-knowledge-v1` remains frozen
- Phase 10 status: DESIGN
- P10-01: READY
- P10-02: BLOCKED_BY_P10-01
- External Design Review: PENDING
- P10-03 onward: BLOCKED_BY_EXTERNAL_DESIGN_REVIEW

## Phase goal

Build a deterministic, replayable, source-backed Evaluation & Calibration Harness for the existing Writing Task 2 learning system so that the repository can answer, with evidence:

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
- new public product features unless strictly necessary to expose already-owned evaluation evidence and explicitly approved by the design contract;
- evaluation data containing secrets, private user data, or uncontrolled production records;
- test assertions that bless current behavior solely because it currently exists.

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

## Dataset principles

The Phase 10 canonical dataset must be repository-safe, reviewable, bounded, and versioned.

It must contain representative categories such as:

1. normal accepted Writing Task 2 evaluations;
2. low / middle / high score profiles;
3. criterion-specific weakness patterns;
4. half-band learner-state cases;
5. repeated episodes that exercise Memory and trend logic;
6. exact Planner tie cases;
7. stale / missing / malformed state or provider payload cases;
8. grounding and provenance cases;
9. Agent direct-answer versus lifecycle-action cases;
10. failure / fallback paths;
11. regression cases promoted from historical bugs;
12. calibration cases with explicit provenance for reference judgments.

The dataset must not copy large copyrighted source passages. It must not depend on network access during normal regression execution.

## Calibration reference principles

P10-02 must freeze what qualifies as calibration evidence.

At minimum:

- every reference label must identify its origin;
- machine-generated reference labels cannot be presented as official examiner truth;
- human labels must record enough metadata to distinguish single-rater opinion from stronger adjudicated evidence;
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

Phase 10 must prefer deterministic evaluators whenever the contract can be checked from structured state.

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
- provider-backed evaluation must be separable from the deterministic core regression suite.

## Dependency graph

```text
START
  -> P10-00 Phase 10 Kickoff / Graph Establishment [COMPLETE]
  -> P10-01 Existing Evaluation Surface Audit [READY]
  -> P10-02 Evaluation & Calibration Contract Freeze [BLOCKED_BY_P10-01]
  -> External Design Review [PENDING]
  -> P10-03 Canonical Eval Case Schemas [BLOCKED_BY_EXTERNAL_DESIGN_REVIEW]
  -> P10-04 Golden Writing Eval Dataset v1
  -> P10-05 Deterministic Outcome Evaluator
  -> P10-06 Trajectory Evaluator
  -> P10-07 Knowledge Grounding Evaluator
  -> P10-08 Authority / Fail-Closed Evaluator
  -> P10-09 Learning Lifecycle Evaluator
  -> P10-10 Writing Score Calibration Analysis
  -> P10-11 Failure Taxonomy & Attribution
  -> P10-12 Eval Runner / Harness
  -> P10-13 Machine-Readable Eval Result & Human Report
  -> P10-14 Regression Corpus Promotion
  -> P10-15 CI-Compatible Deterministic Eval Gate
  -> P10-16 Full Phase 1-10 Regression Validation
  -> P10-17 Documentation / Operator Workflow
  -> P10-18 Internal Final Audit [INTERNAL_AUDIT_COMPLETE target]
  -> External Implementation Review
  -> PR / CI / merge authorization
  -> Phase 10 COMPLETE
  -> STOP (do not start Phase 11)
```

The implementation node order above is the default dependency chain. P10-02 may propose a limited safe parallelization only if it preserves deterministic ownership and External Design Review explicitly approves it.

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

## P10-01 — Existing Evaluation Surface Audit — READY

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

## P10-02 — Evaluation & Calibration Contract Freeze

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
6. deterministic core versus optional provider-backed evaluators.
7. trace/evidence representation.
8. isolation and database lifecycle.
9. canonical dataset storage format.
10. reference-label admissibility and provenance.
11. calibration metrics and interpretation.
12. regression promotion rules.
13. fail-closed behavior.
14. CI gating policy.
15. compatibility rules for historical production versions.
16. provider configuration recording if a secondary judge exists.
17. exact prohibition on private chain-of-thought requirements.
18. update process for golden cases.
19. rules preventing test-data overfitting or silent semantic repair.
20. audit/report evidence required for Phase completion.

### Versioning

P10-02 must choose exact stable identifiers before implementation. Suggested names may include concepts such as:

```text
writing-eval-case-v1
writing-eval-result-v1
writing-eval-suite-v1
writing-score-calibration-v1
```

These names are suggestions only until P10-02 freezes them.

### External Design Review gate

After P10-02:

```text
P10-01 audit
  + P10-02 frozen policy
  + PHASE10_GRAPH.md
  -> External Design Review
```

If review is not APPROVED, remain in DESIGN/FIXING. Do not begin P10-03.

## P10-03 — Canonical Eval Case Schemas

### Dependency

External Design Review APPROVED.

### Objective

Implement strict versioned schemas for canonical eval cases, expected outcomes, execution evidence, evaluator verdicts, failure attribution, and suite results.

### Requirements

- closed enums where the frozen policy requires them;
- explicit version fields;
- stable case IDs;
- no free-form executable code embedded in dataset rows;
- explicit expected authority/evidence references;
- strict validation of unknown evaluator IDs and malformed expectations;
- deterministic serialization suitable for repository review;
- no production database schema migration unless P10-02 demonstrates and explicitly authorizes a need.

### Tests

Prove malformed, duplicate, unsupported-version, unknown-evaluator, and ambiguous required-field cases fail closed.

## P10-04 — Golden Writing Eval Dataset v1

### Objective

Create the bounded canonical v1 dataset using the P10-03 schemas and P10-02 admissibility rules.

### Dataset coverage

Must cover representative success, boundary, and failure cases across:

- evaluator scoring contract;
- accepted/rejected lifecycle transitions;
- learner state;
- Memory and longitudinal history;
- Planner and tie-breaking;
- recommendation ownership;
- Knowledge retrieval / guidance / provenance;
- generation v1/v2 compatibility where required;
- Agent orchestration;
- fallback / malformed-provider paths;
- chronology / freshness mismatches;
- at least one multi-episode learner trajectory.

### Golden-data rules

- every case has rationale;
- every expected value has a declared authority source;
- calibration labels have provenance metadata;
- ambiguous references remain explicitly ambiguous;
- no network dependency for deterministic cases;
- no hidden local files or secrets;
- no production-user records.

The final minimum case count must be justified by coverage, not by an arbitrary large number. P10-02 may freeze category minimums.

## P10-05 — Deterministic Outcome Evaluator

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
- Agent final answer claims consistent with authoritative structured evidence.

## P10-06 — Trajectory Evaluator

### Objective

Verify allowed lifecycle execution from observable application evidence.

### Requirements

- no private chain-of-thought;
- rely on tool/service traces, event IDs, persistence rows, version fields, or other application-owned evidence;
- detect missing, duplicated, reordered, stale, or forbidden transitions where the contract defines order;
- bounded and deterministic.

If required evidence is not observable, add the smallest test-only or non-semantic instrumentation approved by P10-02. Do not add a production behavioral dependency merely for eval convenience.

## P10-07 — Knowledge Grounding Evaluator

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

## P10-08 — Authority / Fail-Closed Evaluator

### Objective

Verify subsystem ownership and failure handling.

### Required coverage

At minimum include cases for:

- malformed provider response;
- unknown IDs / versions;
- stale or mismatched episode/recommendation evidence;
- generator attempting to contradict the recommendation;
- Knowledge attempting to override Planner authority;
- Agent final response claiming an operation succeeded when the operation did not succeed;
- unsupported action or route;
- missing required evidence.

Veto-class authority violations must fail the suite regardless of lower-severity passes elsewhere.

## P10-09 — Learning Lifecycle Evaluator

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

## P10-10 — Writing Score Calibration Analysis

### Objective

Measure agreement between frozen `writing-task2-v1` outputs and admissible reference labels without redefining score semantics.

### Minimum analysis dimensions

Subject to P10-02 final freeze, include appropriate metrics such as:

- exact overall-band agreement;
- within-0.5 and within-1.0 agreement;
- per-criterion absolute error;
- signed bias by criterion;
- distribution of disagreements;
- disagreement by reference-evidence tier;
- explicit sample count and coverage caveats.

Do not present a metric as statistically meaningful when the dataset is too small to support that claim.

### Calibration failure behavior

A material mismatch must produce evidence such as:

```text
case ID
reference provenance
evaluator output
delta
criterion(s)
confidence / ambiguity metadata
```

It must not automatically mutate the rubric or golden label.

## P10-11 — Failure Taxonomy & Attribution

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

## P10-12 — Eval Runner / Harness

### Objective

Build one reproducible entrypoint that executes selected canonical cases in an isolated environment and applies the registered evaluator set.

### Required characteristics

- deterministic core mode works without external model/network access where the tested production path permits it;
- explicit optional provider-backed mode if approved;
- case selection/filtering by stable metadata;
- isolated database state;
- repeatable setup/teardown;
- bounded runtime and output;
- structured machine-readable result;
- non-zero failure exit for gated deterministic failures;
- safe interruption without contaminating later cases;
- no mutation of production-like user data.

The harness may be CLI, pytest-integrated, or another minimal repository-native form. P10-01/P10-02 determine the simplest justified approach; do not add an Eval framework merely for branding.

## P10-13 — Machine-Readable Eval Result & Human Report

### Objective

Produce durable evidence that is both automation-friendly and reviewable.

### Machine-readable output

Must include enough information to reproduce/inspect:

- suite version;
- case IDs and case versions;
- evaluator IDs/versions;
- pass/fail/not-applicable verdicts;
- severity;
- failure attribution;
- relevant production version identifiers;
- calibration deltas where applicable;
- environment/provider metadata allowed by policy;
- timestamps only where they do not break deterministic comparison semantics.

### Human report

Expected Phase artifact:

```text
docs/PHASE10_EVAL_REPORT.md
```

The report must be answer-first and include:

- suite coverage;
- veto failures;
- major failures;
- calibration findings;
- known blind spots;
- provider-dependent exclusions;
- regression status;
- recommended follow-up without silently implementing future-phase changes.

## P10-14 — Regression Corpus Promotion

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

Golden-case edits must be reviewable. Deleting or weakening a regression case requires an explicit rationale and contract change evidence.

## P10-15 — CI-Compatible Deterministic Eval Gate

### Objective

Add the deterministic core suite to CI at a cost and runtime appropriate for the repository.

### Requirements

- provider-free gated path;
- reproducible test/database setup;
- clear command documented locally and in CI;
- veto/major contract failures cause CI failure according to P10-02;
- optional provider/calibration jobs must not masquerade as deterministic gates;
- existing Phase 1–9 test suite remains intact.

If CI runtime is too high, split smoke and full deterministic suites only if the policy defines exactly what remains merge-gating.

## P10-16 — Full Phase 1–10 Regression Validation

### Objective

Run the complete relevant validation stack after Phase 10 integration.

### Required evidence

At minimum capture:

- backend tests;
- frontend/browser checks where existing repository contracts require them;
- database/migration checks even if no migration is expected, when repository standard validation includes them;
- deterministic Eval Harness result;
- calibration analysis result;
- CI-equivalent commands;
- no unexpected production contract changes.

Historical Phase 1–9 behavior must remain compatible unless P10-02 explicitly freezes a justified narrow compatibility exception.

## P10-17 — Documentation / Operator Workflow

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

## P10-18 — Internal Final Audit

### Objective

Verify that Phase 10 satisfies its frozen contract before external implementation review.

### Expected deliverable

```text
docs/PHASE10_AUDIT.md
```

### Audit must prove

1. every frozen P10-02 invariant is implemented or explicitly marked blocked;
2. canonical dataset validates against the frozen schema;
3. deterministic suite is reproducible;
4. veto-class violations fail closed;
5. failure attribution is evidence-backed;
6. Knowledge grounding reuses Phase 9 authority;
7. `writing-task2-v1` semantics were not silently changed;
8. Planner / Memory / Agent authority was not expanded;
9. calibration results preserve reference provenance and disagreement evidence;
10. CI gating matches policy;
11. regression corpus is reviewable;
12. full relevant Phase 1–10 tests pass;
13. no secret, personal production data, or uncontrolled network dependency was introduced;
14. docs match implementation;
15. unresolved limitations are explicit.

Target status after successful audit:

```text
P10-18 = INTERNAL_AUDIT_COMPLETE
Phase 10 = IMPLEMENTATION_COMPLETE_AWAITING_EXTERNAL_REVIEW
```

This status is not authorization to merge.

## External Implementation Review gate

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

Only an approved outcome may proceed to PR/CI/merge authorization according to the repository's normal process.

## Phase completion criteria

Phase 10 is COMPLETE only when all of the following are true:

1. P10-01 through P10-18 are COMPLETE according to the frozen graph/policy.
2. External Design Review is APPROVED.
3. External Implementation Review is APPROVED or the project's explicitly accepted equivalent approval state.
4. deterministic Eval Harness passes its merge-gating suite.
5. calibration report exists with provenance and caveats.
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
- External Design Review or External Implementation Review blocks progress;
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

Current next action after this graph is committed:

```text
P10-01 Existing Evaluation Surface Audit
```

Phase 10 implementation remains unauthorized until the design gate is passed.
