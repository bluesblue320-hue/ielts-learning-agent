# Phase 9 Internal Audit

**Status:** Phase 9 implementation is
`IMPLEMENTATION_COMPLETE_AWAITING_EXTERNAL_REVIEW` on
`phase/9-ielts-knowledge-grounding-v1`. External Design Review is `APPROVED`;
External Implementation Review is `PENDING`. No PR or merge has been created.

## Validation identity

The repaired implementation and browser-test HEAD validated by every command
below is `25e6591763283f485a0361d95c9f17017cb21d85`. The following
documentation-only repair-audit commit does not change runtime or test
behavior. The branch is based on Phase 8 master merge commit
`4739bca53ebcae96f10bca256e3568a644f2fef4`.

## Frozen contract proof

- Knowledge: `ielts-writing-knowledge-v1`.
- Retrieval: `writing-knowledge-structured-v1`.
- Grounded guidance: `writing-grounded-guidance-v1`.
- Practice generation policy: `writing-practice-generation-v2`.
- Practice prompt: `practice-generation-v2`.
- Knowledge context: `writing-practice-knowledge-context-v1`.
- Public guidance: `GET /learners/{learner_id}/writing/guidance`.
- Guidance authority is the latest accepted update ordered exactly by
  `LearningUpdate.id DESC`.

All boundaries are strict, immutable Pydantic models. Knowledge remains
learner-independent; retrieval purpose is a closed strategy selector and is
not stored on `KnowledgeUnit`.

## Source manifest and claim provenance

The checked-in snapshot contains four registered official IELTS sources and 54
stable Knowledge units:

- 4 criterion assessment units;
- 40 integer descriptor anchors (four criteria × bands 0 through 9);
- 3 Writing Task 2 rule units;
- 7 canonical Task 2 prompt-type units.

Every unit has at least one claim-level `KnowledgeSourceRef`; every reference
resolves to the immutable source registry and includes a non-blank locator.
Duplicate Knowledge IDs and unknown source IDs fail closed. Public citations
are resolved by the application from registered source metadata and the exact
retrieved claim locators; a provider cannot supply or rewrite them.

All 40 criterion-by-integer-band descriptor summaries were independently
recalibrated against the registered May 2023 official IELTS Writing Band
Descriptors. Stable Knowledge IDs, `ielts-writing-band-descriptors-2023`
source ownership, and deterministic criterion/band locators remain unchanged.
Targeted semantic regressions protect Task Response Band 5, Coherence and
Cohesion Band 6, and Lexical Resource Bands 5 and 6 from the reviewed adjacent-
band overstatements.

## Deterministic retrieval proof

Retrieval is provider-free and operates only over the Git-versioned snapshot.
It accepts a closed structured query, preserves declaration order, de-duplicates
by stable Knowledge ID, and is bounded by purpose: practice generation 7,
learner guidance 8, rubric compatibility 2.

Official descriptors remain integer-only. Product half-bands select adjacent
official descriptors exactly: 6.0→6, 6.5→6+7, 7.0→7, 7.5→7+8. Band 9.0 is
capped at descriptor 9. No official half-band descriptor is created.

## Rubric compatibility result

P9-06 now uses an explicit deterministic semantic compatibility ledger, not an
inference from Knowledge-ID existence. Exactly 40 reviewed entries bind each
`writing-task2-v1` criterion/band anchor to the frozen rubric-text identity,
mapped Knowledge IDs, frozen Knowledge-statement identity, an explicit status,
and a non-blank semantic rationale. Runtime audit results are projected from
that ledger. Missing, duplicate, extra, unknown-reference, blank-rationale,
invalid-status, rubric-drift, and Knowledge-drift cases all fail closed.

The official-source recalibration produced 23
`compatible_with_missing_provenance` entries and 17
`gap_requires_documentation` entries. The documented gaps are Task Response
Bands 3–8, Coherence and Cohesion Bands 3–8, Lexical Resource Bands 4–7, and
Grammatical Range and Accuracy Band 4. These are meaningful adjacent-band
severity differences between the concise official-source Knowledge and the
historical product rubric; none changes runtime scoring authority. No
`material_conflict` was found. The evaluator wording, scoring, weighting,
product-band aggregation, and half-band behavior remain unchanged.

## Guidance and generation grounding

The guidance service is deterministic and provider-free. It returns a safe
empty projection before the first accepted update. Otherwise it resolves the
latest accepted `LearningUpdate.id DESC`, its owned `PracticeRecommendation`,
and the recommendation's strictly reconstructed immutable `state_snapshot`.
All state values used by the guidance explanation therefore belong to that one
accepted chronology; the endpoint does not query live `LearnerSkillState`
after accepting an update. Corrupt persisted snapshots fail safely.

Every learner-facing guidance explanation is composed from retrieved Knowledge
statements, and each citation resolves to the exact sources/locators used by
those statements. No provider reasoning, chain of thought, raw Planner context,
Memory provenance, or filesystem path is public.

Practice generation v2 receives a bounded application-owned Knowledge context.
The persisted recommendation continues to own WHAT is trained; the provider
only controls HOW the exercise is phrased. Strict output validation rejects a
different target and any injected source or Knowledge identity. Historical
generation v1 reconstruction remains supported and cannot carry Phase 9
context.

## Fresh validation

All results below were produced from
`25e6591763283f485a0361d95c9f17017cb21d85` with an isolated local PostgreSQL
18 cluster and no live DeepSeek or runtime web access.

- Backend: `python -m pytest -q --strict-markers` — **1030 passed**, with one
  existing Starlette/httpx `TestClient` deprecation warning.
- PostgreSQL chronology regression: **1 passed** with explicit thread events;
  update N was selected, N+1 committed, and the response still returned N's
  recommendation plus N's four 5.00 snapshot estimates while live state was
  already N+1's four 7.00 estimates.
- Rubric ledger: all **40/40** explicit reviewed entries and current Knowledge
  hashes validated; runtime preserved all 17 documented gaps, and all negative
  fail-closed ledger tests passed.
- Descriptor snapshot: **40/40** criterion-specific integer-band units passed
  official-source semantic calibration with stable IDs and aligned locators; no
  half-band unit exists.
- Frontend unit: `npm test` — **15 passed**.
- Frontend gates: `npm run lint`, `npm run typecheck`, and `npm run build` —
  all passed.
- Chromium: `npm run test:e2e -- --reporter=line` — **6 passed**.
- Phase 9 browser proof creates and applies an initial Writing evaluation,
  verifies current/target bands, the gap rationale, retrieved requirements,
  two integer-band descriptor locators, official source URLs, absence of raw
  Knowledge/source IDs, and exact grounded content after dashboard reload.
- Alembic: exactly one head,
  `0006_submission_claim_recovery (head)`.

## Frozen boundaries and forbidden-scope audit

The master-to-implementation diff adds no migration and does not change ORM
models, learner-state computation, Planner v1/v2 selection, Memory tie-break
semantics, Core Agent bounds, practice idempotency/freshness fences, or the
frozen `writing-task2-v1` evaluator/scoring semantics. It adds no dependency.

No vector database, embedding pipeline, generic RAG framework, LangChain,
LangGraph, Redis, Celery, Kafka, multi-agent runtime, LLM planner/router,
runtime web search/crawling, Reading, Listening, Speaking, authentication,
payments, microservices, or new migration was introduced.

## Known limitations

- The v1 snapshot is deliberately concise, static, English-language, and
  Writing Task 2–only; source refresh remains an explicit reviewed Git change.
- Existing `writing-task2-v1` rubric text retains its historical missing-
  provenance caveat and the 17 documented semantic gaps above; Phase 9 does not
  rewrite it or change scoring.
- Retrieval is intentionally structured rather than semantic; no arbitrary
  corpus query or public Knowledge search endpoint exists.
- External Implementation Review, PR/CI, merge authorization, and master merge
  remain pending.

## Status

P9-01 through P9-12 are `COMPLETE`; P9-13 is
`INTERNAL_AUDIT_COMPLETE`. Phase 9 implementation is
`IMPLEMENTATION_COMPLETE_AWAITING_EXTERNAL_REVIEW`. External Design Review is
`APPROVED`; External Implementation Review is `PENDING`.

STOP. Do not begin another phase, open a PR, or merge without explicit
authorization.
