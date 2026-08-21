# IELTS Knowledge Policy

## Contract status

**Frozen Phase 9 P9-02 design contract — External Design Review APPROVED.**

This policy defines the normative v1 boundary for IELTS Writing Task 2 Knowledge,
structured retrieval, provenance, grounded learner guidance, and
Knowledge-grounded practice generation.

- Knowledge version: `ielts-writing-knowledge-v1`
- Retrieval version: `writing-knowledge-structured-v1`
- Grounded guidance version: `writing-grounded-guidance-v1`
- Task scope: `writing_task2`
- Runtime source of truth for learner data: PostgreSQL
- Product-policy source of truth for Knowledge v1: Git-versioned static snapshot
- Retrieval style: deterministic structured retrieval
- Runtime internet dependency: none
- Embeddings/vector DB: forbidden in v1
- Scoring-semantic change: forbidden in v1
- Descriptor bands: integer 0..9 only
- Learner bands: Decimal values in .0/.5 increments
- Guidance API: `GET /learners/{learner_id}/writing/guidance`
- Practice generation policy: `writing-practice-generation-v2`
- Practice prompt: `practice-generation-v2`
- Knowledge context version: `writing-practice-knowledge-context-v1`

## 1. Responsibility boundary

Keep these authorities separate:

```text
Learner State
= current persisted estimate of this learner

Learning Memory
= durable history and deterministic longitudinal patterns for this learner

Planner
= persisted decision about WHAT the learner should train next

IELTS Knowledge
= learner-independent reference knowledge about IELTS Writing Task 2

Generator / Evaluator
= bounded qualitative model services under application-owned contracts

Core Learning Agent
= deterministic controller deciding WHEN an allowed operation runs
```

IELTS Knowledge is not a generic memory blob, planner, evaluator, autonomous
researcher, or Agent runtime.

Knowledge does not own:

- learner target score;
- learner skill state;
- practice target skill;
- planner reason codes;
- planner version;
- learning-update chronology;
- evaluation persistence;
- score aggregation;
- lifecycle state;
- Agent action selection.

## 2. Source authority policy

### 2.1 Allowed source tiers

Phase 9 v1 may curate only official IELTS ecosystem sources.

**Tier 1 — primary**

- IELTS official global material (`ielts.org`);
- official IELTS Writing assessment/band-descriptor material;
- official IELTS Writing Task 2 preparation/task-understanding material.

**Tier 2 — allowed when needed and non-conflicting**

- British Council official IELTS material;
- IDP official IELTS material.

Tier 2 may supplement but must not silently override Tier 1.

### 2.2 Forbidden authoritative sources in v1

- commercial test-prep blogs;
- teacher/influencer posts;
- Reddit/forums/social media;
- model-generated explanations without official provenance;
- scraped question banks with unclear rights/provenance;
- unverified mirrors.

### 2.3 No runtime web dependency

The running application must not:

- search the web;
- crawl official pages;
- fetch URLs to answer a learner;
- dynamically replace Knowledge based on network content.

Knowledge is curated and reviewed ahead of release. Freshness is metadata.

## 3. Source record contract

Every curated source has a stable application-owned identity.

Conceptual shape:

```python
KnowledgeSource(
    source_id="ielts-writing-band-descriptors-2023",
    authority="official_ielts",
    publisher="IELTS",
    title="...",
    url="https://...",
    source_type="official_web_or_pdf",
    verified_at="YYYY-MM-DD",
    content_scope=["writing_task2"],
    source_revision="2023-05",
)
```

Knowledge claims do not point to a source ID alone. They use a source reference:

```python
KnowledgeSourceRef(
    source_id="ielts-writing-band-descriptors-2023",
    locator="Task 2 / Task Response / Band 7",
    page=1,
    section="Task Response",
)
```

Rules:

- `source_id` is stable and unique;
- `authority` is a closed enum;
- URL is provenance, not a runtime fetch target;
- `verified_at` records curation time;
- title/publisher are safe public metadata;
- `source_revision` or equivalent records the authoritative source revision when
  known;
- claim-level references include a deterministic locator (section/page/band/task
  as applicable);
- source text is not copied wholesale.

## 4. Knowledge unit contract

Knowledge is split into small structured units.

Conceptual shape:

```python
KnowledgeUnit(
    knowledge_id="writing-tr-band7-developed-position",
    knowledge_version="ielts-writing-knowledge-v1",
    task="writing_task2",
    category="assessment",
    criterion="task_response",
    descriptor_band=7,
    task_type=None,
    statement="Concise product-safe summary.",
    source_refs=[KnowledgeSourceRef(...)],
)
```

### 4.1 Required dimensions

v1 must represent:

- task;
- category;
- criterion where applicable;
- integer `descriptor_band` 0..9 where applicable;
- Task 2 task type where applicable;
- concise product-owned statement;
- one or more source references;
- stable `knowledge_id`;
- `knowledge_version`.

### 4.2 v1 categories

1. **assessment criteria**
   - Task Response;
   - Coherence and Cohesion;
   - Lexical Resource;
   - Grammatical Range and Accuracy.

2. **band guidance**
   - concise learning-oriented summaries;
   - no wholesale copying of official descriptors.

3. **Task 2 rules**
   - minimum length / format expectations where officially supported;
   - relevance;
   - position/idea-development expectations;
   - other source-backed Task 2 requirements.

4. **Task understanding**
   - `opinion`;
   - `discussion`;
   - `multi_part`;
   - `multi_part_opinion`;
   - `advantage_disadvantage`;
   - `positive_negative`;
   - `cause_solution`.

These are the canonical Knowledge-layer task-type identifiers for v1. UI labels
may use friendlier aliases, but the Knowledge layer must not invent a conflicting
taxonomy and present it as official.

### 4.3 Learner independence

Knowledge units must never contain:

- learner ID;
- learner score/state;
- essay text;
- practice ID;
- recommendation ID;
- LearningUpdate ID;
- Memory trend/persistent gap;
- provider reasoning;
- claim token;
- browser cache state.

## 5. Half-band interpretation policy

Official descriptor Knowledge units are integer-band units only.

Learner state may remain on the product's existing Decimal half-band scale. The
retriever maps learner bands to descriptor context deterministically:

```text
6.0 -> descriptor 6
6.5 -> lower descriptor 6 + upper descriptor 7
7.0 -> descriptor 7
7.5 -> lower descriptor 7 + upper descriptor 8
```

General rule:

```text
x.0 -> descriptor x
x.5 -> descriptors x and x+1
```

The application may explain a half-band as an in-between learner state, but it
must never fabricate an "official Band 6.5 descriptor" or equivalent source
claim.

Target-band retrieval follows the same mapping. When current and target bands
map to overlapping descriptors, the retrieval strategy de-duplicates Knowledge
IDs while preserving deterministic order.

## 6. Versioning policy

Initial version:

`ielts-writing-knowledge-v1`

A new version is required when meaning can change, including:

- changed assessment interpretation;
- changed Task 2 rule;
- changed band progression guidance;
- changed retrieval-relevant taxonomy.

Pure typo/URL maintenance may keep the version if meaning is unchanged.

Phase 9 defaults to **no new database table or column**. Source control versions
the reference knowledge.

## 7. Structured retrieval contract

Retrieval version:

`writing-knowledge-structured-v1`

Retrieval is deterministic application logic, not an LLM search.

Conceptual request:

```python
retrieve_knowledge(
    task="writing_task2",
    purpose="practice_generation",
    criterion="task_response",
    current_band="6.0",
    target_band="7.0",
)
```

### 7.1 Retrieval purpose semantics

`purpose` belongs to the retrieval query, not to `KnowledgeUnit` metadata.
Knowledge remains learner-independent and application-purpose-independent.

Frozen v1 purposes:

```text
practice_generation
learner_guidance
rubric_compatibility
```

Each purpose selects one deterministic retrieval strategy. The strategy defines
which Knowledge metadata is filtered and how results are ranked.

Examples:

```text
practice_generation
-> exact criterion
-> target descriptor context
-> criterion-general guidance
-> relevant Task 2 global rules

learner_guidance
-> exact criterion
-> current descriptor context
-> target descriptor context
-> progression guidance
-> relevant global rules

rubric_compatibility
-> exact criterion
-> exact descriptor band
-> provenance units needed for comparison
```

### 7.2 Allowed query dimensions

- task;
- purpose;
- criterion;
- current band;
- target band;
- task type where modeled.

### 7.3 Forbidden query dimensions

- arbitrary free-form query;
- raw essay text;
- raw learner Memory;
- embedding vectors;
- provider reasoning;
- URLs to fetch;
- hidden prompt instructions.

### 7.4 Deterministic selection

For the same Knowledge version and normalized query, return the same ordered
Knowledge IDs.

There is no `purpose` field on Knowledge units and therefore no
`task + purpose + criterion` metadata match. Purpose chooses the strategy first;
the selected strategy then ranks exact Knowledge metadata matches.

The exact ranking must be encoded and tested.

### 7.5 Bounded retrieval

Each purpose has an explicit small result bound. Do not send the whole corpus to
a provider by default.

## 8. Provenance and citation policy

Citation is application-owned:

```text
retriever
  -> knowledge_id(s)
  -> source_id(s)
  -> safe source projection
  -> UI / grounded response
```

An LLM may not invent or select a new source identity.

A claim such as "According to IELTS official guidance..." is forbidden unless an
application-selected source backs it.

If provider output returns an unknown source/citation, the application rejects,
strips, or ignores it according to strict schema. It never promotes it into
authoritative provenance.

## 9. Existing Writing rubric compatibility

Existing evaluator rubric:

`writing-task2-v1`

remains frozen through Phase 9 unless separately reviewed.

P9-06 must compare current product rubric semantics with the curated official
Knowledge snapshot.

Allowed outcomes:

```text
compatible
compatible_with_missing_provenance
gap_requires_documentation
material_conflict
```

For `material_conflict`:

```text
STOP
-> document exact conflict
-> keep writing-task2-v1 unchanged
-> design writing-task2-v2 separately
-> require External Design Review
```

Phase 9 must not:

- recalculate historical scores;
- rewrite evaluations;
- change product-band aggregation;
- change criterion weighting;
- change learner-state EWMA behavior;
- change Planner semantics.

## 10. Grounded learner guidance

Guidance version:

`writing-grounded-guidance-v1`

Guidance combines:

```text
persisted learner state / recommendation
+
deterministically retrieved IELTS Knowledge
+
safe presentation rules
```

Typical output may include:

- current skill estimate;
- target;
- gap;
- concise "what IELTS expects";
- next-practice rationale;
- source/provenance entries.

Guidance is explanatory only and does not mutate learner state.

### 10.1 Language

UI remains Chinese-first while IELTS criterion names remain recognizable:

- 任务回应（Task Response）
- 连贯与衔接（Coherence and Cohesion）
- 词汇资源（Lexical Resource）
- 语法多样性与准确性（Grammatical Range and Accuracy）

### 10.2 LLM use

Prefer deterministic templates in v1.

If model wording is later used:

- application selects all Knowledge first;
- input is structured;
- output is validated;
- Knowledge/source IDs cannot change;
- no chain-of-thought is stored/exposed;
- provider failure cannot corrupt state;
- deterministic fallback should exist where practical.

## 11. Knowledge-grounded practice generation

Phase 9 may extend the existing generator request with versioned Knowledge
context.

This is a semantic generation-boundary change, so Phase 9 freezes new versions:

```text
GENERATION_POLICY_VERSION = writing-practice-generation-v2
PRACTICE_PROMPT_VERSION = practice-generation-v2
KNOWLEDGE_CONTEXT_VERSION = writing-practice-knowledge-context-v1
```

Existing `writing-practice-generation-v1` / `practice-generation-v1` semantics
remain immutable for historical practices.

Frozen rule:

```text
Persisted PracticeRecommendation decides WHAT
Knowledge grounds reference expectations
Generator decides HOW
```

Knowledge must not override:

- `target_skill`;
- `learner_target_band`;
- `reason_codes`;
- `planner_version`;
- recommendation ownership;
- Agent freshness fences.

Learning Memory remains Planner exact-tie-only input and is not supplied to the
generator.

Send only minimal Knowledge summaries/IDs, not raw official documents.

## 12. Grounded guidance authority and public API

The current learner authority for grounded guidance is the latest accepted
`LearningUpdate` ordered exactly by:

```text
LearningUpdate.id DESC
```

Do not use timestamp ordering and do not use browser cache as authority.

Guidance is built from the learner state and current `PracticeRecommendation`
owned by that accepted chronology plus deterministic Knowledge retrieval.

Phase 9 v1 exposes exactly one new public read endpoint:

```http
GET /learners/{learner_id}/writing/guidance
```

Response version:

`writing-grounded-guidance-v1`

The safe response contains:

- learner-state summary needed for explanation;
- current recommendation summary;
- grounded guidance items;
- source citations;
- `guidance_version`;
- `knowledge_version`;
- `retrieval_version`.

The endpoint must not expose:

- raw planner context snapshots;
- Memory provenance blobs;
- claim tokens/timestamps;
- provider reasoning;
- arbitrary Knowledge corpus search;
- internal filesystem paths.

No `GET /knowledge/search?q=...` or equivalent generic query API is authorized.

## 13. Core Learning Agent compatibility

Phase 8 Agent v1 remains deterministic and bounded.

Phase 9 does not authorize:

- new natural-language Agent Turn input;
- LLM routing;
- free-form tool selection;
- background agent;
- autonomous research;
- generic tool registry;
- extra loop iterations.

Knowledge integration should sit inside existing service boundaries.

## 14. Persistence policy

Default:

**no new table and no migration.**

Reason:

- Knowledge v1 is product-policy/reference data;
- Git already versions it;
- corpus is small;
- it is learner-independent;
- runtime network update is forbidden.

Any future persistence need must route back to design review.

## 15. Failure behavior

Fail closed:

- unknown Knowledge ID -> configuration/application error;
- unknown source ID -> configuration/application error;
- invalid query enum -> validation error;
- impossible band/criterion combination -> explicit retrieval failure;
- missing provenance -> test/startup failure;
- provider citation injection -> schema rejection or safe discard.

Do not fabricate an explanation when required authoritative Knowledge is
missing.

## 16. Test contract

Phase 9 must prove:

- source registry uniqueness;
- Knowledge ID uniqueness;
- all source references resolve;
- version consistency;
- stable ordering;
- structured retrieval exact matches/fallbacks;
- bounded result count;
- retrieval makes no provider/network call;
- rubric compatibility;
- safe guidance citations;
- provider cannot inject provenance;
- Planner/Memory/Agent invariants remain intact;
- practice lifecycle/freshness regressions remain green;
- Chinese-first browser grounding UX;
- no live DeepSeek or web dependency in CI.

## 17. Copyright/content rule

Store concise product-owned summaries and metadata rather than reproducing large
portions of official copyrighted descriptors or preparation pages.

Use source URLs/IDs for provenance. Exact excerpts, if ever necessary, must be
minimal and separately reviewed.

## 18. Explicitly forbidden v1 technologies and scope

```text
pgvector
Milvus
Qdrant
Elasticsearch
vector search
embedding pipelines
generic RAG frameworks
LangChain
LangGraph
Redis
Celery
Kafka
multi-agent
LLM planner/router
runtime web search
automatic web crawling
fine-tuning
Reading
Listening
Speaking
authentication
payments
microservices
```

## 19. Evolution trigger for semantic retrieval

Semantic retrieval may be reconsidered only after the corpus materially grows,
for example:

- large official/preparation document collections;
- example-essay corpus;
- grammar/vocabulary curriculum;
- large tagged question bank;
- teacher-authored learning content.

Structured filters, source ownership, and provenance remain authoritative even
then.

## 20. Phase boundary

Before implementation:

```text
P9-01 COMPLETE
P9-02 COMPLETE
External Design Review = APPROVED
```

Then create:

`phase/9-ielts-knowledge-grounding-v1`

and execute P9-03 through P9-13 under `docs/DEVELOPMENT_LOOP.md`.

At P9-13:

```text
STOP
-> External Implementation Review
-> PR
-> CI
-> explicit merge authorization
```

Do not start the next phase automatically.
