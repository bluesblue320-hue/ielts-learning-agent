# Phase 9 — IELTS Knowledge Layer & Grounded Learning v1

## Document status

**DESIGN CONTRACT FROZEN — External Design Review APPROVED.**

Phase 8 is COMPLETE and merged to `master` through PR #12. Phase 9 begins with a
Writing Task 2–only, versioned IELTS Knowledge Layer. P9-01 baseline audit and
P9-02 contract freeze are complete in this design document. External Design
Review is APPROVED; implementation may begin from P9-03 on the dedicated
Phase 9 branch.

- Repository: `bluesblue320-hue/ielts-learning-agent`
- Phase 8 merge commit / Phase 9 design base:
  `4739bca53ebcae96f10bca256e3568a644f2fef4`
- Knowledge version: `ielts-writing-knowledge-v1`
- Retrieval version: `writing-knowledge-structured-v1`
- Grounded guidance version: `writing-grounded-guidance-v1`
- Scope: IELTS Writing Task 2 only
- Persistence default: Git-versioned static knowledge; no new PostgreSQL table
- Retrieval default: deterministic structured retrieval; no embeddings/vector DB
- Descriptor bands: integer 0..9 only; learner bands remain Decimal .0/.5
- Guidance API: `GET /learners/{learner_id}/writing/guidance`
- Generation policy v2: `writing-practice-generation-v2`
- Practice prompt v2: `practice-generation-v2`
- Knowledge context version: `writing-practice-knowledge-context-v1`
- External Design Review: APPROVED
- Phase 9 implementation: IN_PROGRESS

## Phase goal

Build a Writing-first, versioned, source-backed IELTS Knowledge Layer that
deterministically retrieves authoritative guidance and grounds learner
explanations and practice generation without changing learner-state, Planner, or
scoring semantics.

```text
Learning Memory
= what this learner has done and how the learner is changing

IELTS Knowledge
= what IELTS Writing Task 2 requires and how the product explains those
  requirements
```

## Dependency graph

```text
START
  -> P9-01 Baseline & Knowledge Gap Audit [COMPLETE]
  -> P9-02 Knowledge Source / Provenance / Retrieval Contract Freeze [COMPLETE]
  -> External Design Review [APPROVED]
  -> P9-03 Versioned Knowledge Schemas [COMPLETE]
  -> P9-04 Official Writing Task 2 Knowledge Snapshot v1 [COMPLETE]
  -> P9-05 Deterministic Structured Retriever [COMPLETE]
  -> P9-06 Existing Rubric Provenance & Compatibility Audit [COMPLETE]
  -> P9-07 Grounded Learner Guidance Service [COMPLETE]
  -> P9-08 Knowledge-Grounded Practice Generation [COMPLETE]
  -> P9-09 Public Knowledge / Guidance API [COMPLETE]
  -> P9-10 Chinese-First Grounded Explanation UX [COMPLETE]
  -> P9-11 Grounding / Citation / Hallucination Tests [COMPLETE]
  -> P9-12 Agent + Lifecycle + Browser Regression [COMPLETE]
  -> P9-13 Internal Final Audit [READY]
  -> External Implementation Review [PENDING]
  -> Phase 9 [PENDING]
  -> STOP
```

## P9-01 — Baseline & Knowledge Gap Audit — COMPLETE

The audit is anchored to Phase 8 merge commit
`4739bca53ebcae96f10bca256e3568a644f2fef4`.

Current system findings:

1. No independent IELTS Knowledge domain exists.
2. Existing Writing rubric is a static product-owned module:
   `app/evaluators/rubrics/writing_task2_v1.py`.
3. Existing scoring semantics are already depended on by Phases 2–8.
4. Practice generation receives recommendation authority only; the persisted
   recommendation owns WHAT and the generator owns HOW.
5. Current Writing Task 2 reference corpus is small and highly structured.
6. Learning Memory already models learner history and longitudinal patterns.
7. PostgreSQL stores learner-owned mutable runtime state.
8. Core Learning Agent v1 is deterministic and bounded.
9. Browser UX is Chinese-first while IELTS task content remains English where
   appropriate.
10. Provider outputs are validated before entering application logic.
11. No semantic-retrieval requirement has been demonstrated.
12. Runtime web dependency would weaken determinism and reproducibility.

### P9-01 conclusion

Phase 9 needs:

```text
Official source
  -> curated/versioned Knowledge source record
  -> structured Knowledge units
  -> deterministic retrieval
  -> grounded application service
  -> existing evaluator/practice/Agent surfaces
```

It does not need a generic RAG runtime.

## P9-02 — Contract Freeze — COMPLETE

The normative contract is frozen in
[`IELTS_KNOWLEDGE_POLICY.md`](IELTS_KNOWLEDGE_POLICY.md).

Frozen decisions:

1. Writing Task 2 only.
2. `ielts-writing-knowledge-v1`.
3. `writing-knowledge-structured-v1`.
4. `writing-grounded-guidance-v1`.
5. Git-versioned static Knowledge is the v1 source of truth.
6. No new table or migration is expected in Phase 9.
7. Deterministic structured retrieval only.
8. Official IELTS ecosystem sources only in v1.
9. Existing `writing-task2-v1` scoring semantics remain frozen.
10. Knowledge may ground explanation and generation but may not control Planner
    decisions.
11. Citation/provenance is assembled by application code, never invented by an
    LLM.
12. No runtime web search, crawling, embedding, vector DB, or generic RAG
    framework.
13. Official descriptor units use integer bands only; half-band learner states
    map deterministically to lower+upper integer descriptors.
14. Retrieval `purpose` selects a deterministic strategy and is not stored as
    KnowledgeUnit metadata.
15. Claim-level provenance uses source locators (section/page/band/task), not
    source ID alone.
16. Phase 9 practice generation is versioned as v2 and must not redefine v1.
17. Current grounded guidance authority uses latest accepted
    `LearningUpdate.id DESC` and the one frozen read endpoint.

## Implementation node definitions

### P9-03 — Versioned Knowledge Schemas

- Add strict immutable schemas for source records, Knowledge units, retrieval
  queries/results, citations, and grounded guidance.
- Exact versions and closed enums.
- Descriptor-band schema is integer-only (0..9); learner-band inputs remain
  Decimal half-band capable.
- Provenance uses `KnowledgeSourceRef` with source locator metadata.
- Every Knowledge unit must resolve to known source IDs.
- No learner-specific state in Knowledge units.
- No migration.

### P9-04 — Official Writing Task 2 Knowledge Snapshot v1

Curate product-safe, concise, versioned knowledge in these categories:

- assessment criteria;
- band guidance;
- Task 2 rules;
- Task 2 prompt/requirement categories.

Frozen Task Type taxonomy:

```text
opinion
discussion
multi_part
multi_part_opinion
advantage_disadvantage
positive_negative
cause_solution
```

Only approved official IELTS ecosystem sources are allowed. No runtime scraping,
third-party blogs, forums, or large copied passages. Every unit must carry
provenance and stable IDs.

### P9-05 — Deterministic Structured Retriever

Allowed query dimensions:

- task;
- purpose;
- criterion;
- current band;
- target band;
- task type where modeled.

`purpose` is not Knowledge metadata. It selects one frozen retrieval strategy,
such as `practice_generation`, `learner_guidance`, or
`rubric_compatibility`, and that strategy determines deterministic filters and
ranking over learner-independent Knowledge units.

Half-band mapping is frozen:

```text
6.0 -> descriptor 6
6.5 -> lower descriptor 6 + upper descriptor 7
7.0 -> descriptor 7
7.5 -> lower descriptor 7 + upper descriptor 8
```

No Knowledge unit may claim to be an official half-band descriptor.

Forbidden:

- arbitrary free-form query;
- raw essay;
- Memory blobs;
- embeddings;
- provider reasoning.

Same normalized input and same Knowledge version must produce the same ordered
Knowledge IDs. Result payloads are bounded and provider-free.

### P9-06 — Existing Rubric Provenance & Compatibility Audit

Compare the existing `writing-task2-v1` product rubric with the curated official
Knowledge snapshot.

Do not change scoring behavior.

If a material semantic conflict is found:

```text
STOP
-> document the conflict
-> keep writing-task2-v1 unchanged
-> design writing-task2-v2 separately
-> require another External Design Review
```

### P9-07 — Grounded Learner Guidance Service

Authority remains:

```text
learner state -> where the learner is
Planner       -> what to train
Knowledge     -> what IELTS expects
service       -> grounded explanation
```

Prefer deterministic templates. If model wording is later used, all Knowledge is
selected by the application first and citations remain application-owned.

### P9-08 — Knowledge-Grounded Practice Generation

Extend the generator boundary in a versioned way so it receives the minimum
relevant Knowledge context.

Frozen versions for Phase 9 generated practice:

```text
GENERATION_POLICY_VERSION = writing-practice-generation-v2
PRACTICE_PROMPT_VERSION = practice-generation-v2
KNOWLEDGE_CONTEXT_VERSION = writing-practice-knowledge-context-v1
```

Historical v1 generated practices retain their original semantics forever.

Frozen rule:

```text
Persisted recommendation decides WHAT
Knowledge constrains/grounds reference expectations
Generator decides HOW
```

Knowledge must not override target skill, target band, reason codes, planner
version, ownership, or Agent freshness fences. Memory is still not supplied to
the generator.

### P9-09 — Public Knowledge / Guidance API

Add exactly one public read-only learner-scoped Writing guidance endpoint:

```http
GET /learners/{learner_id}/writing/guidance
```

The response version is `writing-grounded-guidance-v1` and returns only safe
learner-state summary, current recommendation summary, grounded guidance items,
source citations, `guidance_version`, `knowledge_version`, and
`retrieval_version`.

Current authority is the latest accepted learner update ordered exactly by
`LearningUpdate.id DESC`; guidance must use the state and recommendation owned by
that accepted chronology.

No generic corpus search API, runtime URL fetch, source editing, or CMS.

### P9-10 — Chinese-First Grounded Explanation UX

Show:

- current level / target;
- concise gap explanation;
- "what IELTS expects";
- next-practice rationale;
- safe source/provenance labels.

Do not use raw internal IDs as primary UX and do not claim "IELTS officially
says" without application-owned provenance.

### P9-11 — Grounding / Citation / Hallucination Tests

Prove:

- every public citation resolves to a registered source;
- every guidance claim is backed by retrieved Knowledge;
- provider output cannot inject a new source ID;
- unknown Knowledge/source IDs fail closed;
- retrieval ordering is deterministic;
- CI requires no live web or DeepSeek.

### P9-12 — Agent + Lifecycle + Browser Regression

Prove Phase 9 enriches the current loop without changing Phase 2–8 authority:

- initial Writing bootstrap unchanged;
- Agent turn semantics unchanged unless separately reviewed;
- Planner v1/v2 reconstruction remains valid;
- Memory remains Planner exact-tie-only input;
- generation/submission freshness fences remain green;
- practice idempotency remains green;
- browser E2E proves grounded explanation and durable resume.

### P9-13 — Internal Final Audit

Record:

- exact final HEAD;
- test counts;
- source manifest integrity;
- deterministic retrieval proof;
- rubric compatibility result;
- citation/grounding proof;
- forbidden-scope audit;
- migration statement;
- known limitations.

Then STOP for External Implementation Review.

## Explicitly forbidden in Phase 9

```text
pgvector
Milvus
Qdrant
Elasticsearch
embedding pipelines
generic RAG frameworks
LangChain
LangGraph
multi-agent architecture
LLM planner/router
runtime web search
automatic web crawling
Redis
Celery
Kafka
fine-tuning
Reading
Listening
Speaking
authentication
payments
microservices
```

## Phase boundary

When P9-13 is complete:

```text
STOP
-> External Implementation Review
-> PR / CI
-> explicit merge authorization
```

Do not start another phase automatically.
