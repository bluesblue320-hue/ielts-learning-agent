# Phase 9 Internal Audit

**Status:** Phase 9 implementation is
`IMPLEMENTATION_COMPLETE_AWAITING_EXTERNAL_REVIEW` on
`phase/9-ielts-knowledge-grounding-v1`. External Design Review is `APPROVED`;
External Implementation Review is `PENDING`. No PR or merge has been created.

## Validation identity

The implementation and browser-test HEAD validated by every command below is
`370e452b18970ffcb06812afe7a554b51656a447`. The documentation-only P9-13
audit commit follows that validated HEAD and does not change runtime or test
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

## Deterministic retrieval proof

Retrieval is provider-free and operates only over the Git-versioned snapshot.
It accepts a closed structured query, preserves declaration order, de-duplicates
by stable Knowledge ID, and is bounded by purpose: practice generation 7,
learner guidance 8, rubric compatibility 2.

Official descriptors remain integer-only. Product half-bands select adjacent
official descriptors exactly: 6.0→6, 6.5→6+7, 7.0→7, 7.5→7+8. Band 9.0 is
capped at descriptor 9. No official half-band descriptor is created.

## Rubric compatibility result

All 40 existing `writing-task2-v1` criterion/band anchors map to resolving
Phase 9 Knowledge IDs. The recorded result is
`compatible_with_missing_provenance`: the frozen product rubric dimensions and
integer coverage are compatible, while its historical wording did not carry
claim provenance. There is no material conflict and no scoring wording,
aggregation, half-band, provider, or persistence semantic was changed.

## Guidance and generation grounding

The guidance service is deterministic and provider-free. It returns a safe
empty projection before the first accepted update, otherwise uses the
authoritative persisted recommendation and state. Every learner-facing
guidance explanation is composed from retrieved Knowledge statements, and
each citation resolves to the exact sources/locators used by those statements.
No provider reasoning, chain of thought, raw Planner context, Memory provenance,
or filesystem path is public.

Practice generation v2 receives a bounded application-owned Knowledge context.
The persisted recommendation continues to own WHAT is trained; the provider
only controls HOW the exercise is phrased. Strict output validation rejects a
different target and any injected source or Knowledge identity. Historical
generation v1 reconstruction remains supported and cannot carry Phase 9
context.

## Fresh validation

All results below were produced from
`370e452b18970ffcb06812afe7a554b51656a447` with an isolated local PostgreSQL
18 cluster and no live DeepSeek or runtime web access.

- Backend: `python -m pytest -q --strict-markers` — **1012 passed**, with one
  existing Starlette/httpx `TestClient` deprecation warning.
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
- Existing `writing-task2-v1` rubric text retains the documented historical
  missing-provenance caveat; Phase 9 does not rewrite it.
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
