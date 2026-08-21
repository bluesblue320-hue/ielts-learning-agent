# AGENTS.md

# IELTS Learning Agent

## 1. Project Goal

IELTS Learning Agent is an agentic learning system for IELTS preparation.

The long-term system should:

* maintain structured learner state,
* track skill mastery and weaknesses,
* evaluate learning outcomes,
* maintain learning memory,
* dynamically plan future learning tasks,
* provide adaptive IELTS training,
* support Writing, Speaking, Reading, and Listening.

The project should evolve toward a closed learning loop:

```text
Goal
→ Observe
→ Plan
→ Practice
→ Evaluate
→ Update Learner State
→ Store Memory
→ Replan
```

Do not reduce the system to a simple chatbot or LLM wrapper.

---

## 2. Current Development Phase

Always inspect the current phase documentation before implementing features.

Current phase:

```text
Phase 8 — Core Learning Agent Orchestration v1
```

Read:

```text
docs/PHASE8_GRAPH.md
docs/CORE_LEARNING_AGENT_POLICY.md
docs/DEVELOPMENT_LOOP.md
```

Phase 8 status:

```text
Phase 1 = COMPLETE
Phase 2 = COMPLETE
Phase 3 = COMPLETE
Phase 4 = COMPLETE
Phase 5 = COMPLETE
Phase 6 = COMPLETE
P6-01 = COMPLETE
P6-02 = COMPLETE
P6-03 = COMPLETE
P6-04 = COMPLETE
P6-05 = COMPLETE
P6-06 = COMPLETE
P6-07 = COMPLETE
P6-08 = COMPLETE
P6-09 = COMPLETE
P6-10 = COMPLETE
P6-11 = COMPLETE
P6-12 = COMPLETE
P6-13 = COMPLETE
P6-14 = COMPLETE
P6-15 = COMPLETE
P6-16 = INTERNAL_AUDIT_COMPLETE
External Review = APPROVED
PR #10 = MERGED
Phase 7 = COMPLETE
P7-01 = COMPLETE
P7-02 = COMPLETE
P7-03 = COMPLETE
P7-04 = COMPLETE
P7-05 = COMPLETE
P7-06 = COMPLETE
P7-07 = COMPLETE
P7-08 = COMPLETE
P7-09 = COMPLETE
P7-10 = COMPLETE
P7-11 = COMPLETE
P7-12 = COMPLETE
P7-13 = COMPLETE
P7-14 = INTERNAL_AUDIT_COMPLETE
Phase 7 External Design Review = APPROVED
Phase 7 External Implementation Review = APPROVED
PR #11 = MERGED
PR CI = SUCCESS
Master merge CI = SUCCESS
P8-01 = COMPLETE
P8-02 = COMPLETE
P8-03 = COMPLETE
P8-04 = COMPLETE
P8-05 = COMPLETE
P8-06 = COMPLETE
P8-07 = COMPLETE
P8-08 = COMPLETE
P8-09 = COMPLETE
P8-10 = COMPLETE
P8-11 = COMPLETE
P8-12 = COMPLETE
P8-13 = INTERNAL_AUDIT_COMPLETE
Phase 8 = COMPLETE
External Design Review = APPROVED
External Implementation Review = APPROVED
Phase 9 = NOT_STARTED
```

Phase 6 design (P6-01 audit, P6-02 contract freeze, versions
`writing-memory-v1` / `writing-progress-v1`) and the full implementation
(P6-03 through P6-16) are complete. The hierarchical Learning Memory
subsystem is implemented as read models over the existing durable Writing
history: L0 episodes anchor on `LearningUpdate` (no duplicate storage), L1
atoms are projections of persisted rows, L2 longitudinal patterns (trend,
persistent gap, recency windows) and the L3 learner profile are computed
deterministically with exact `Decimal` arithmetic, and the four frozen read
APIs (`/writing/history`, `/writing/history/{episode_id}`, `/writing/progress`,
`/writing/context`) expose them with full provenance. The web product adds
`/history`, `/progress`, and a server-authoritative dashboard resume. No new
database table, no migration, and no provider abstraction were introduced.
Phase 6 was merged to master through PR #10 (merge commit
`b8e419d8c146c921539f4654b5aeb0b56ed6f425`); see
[docs/PHASE6_AUDIT.md](docs/PHASE6_AUDIT.md) for its audit evidence.

Phase 7 is COMPLETE and merged to master through PR #11 (PR head
`f6990ab94f590f1a37122ea0bf12bf7e5218c727`, merge commit
`cbf1ebabc87ec490f74957d1327037dae4242381`). It activates the deterministic
`writing-practice-gap-memory-v2` planner for new Writing evaluations while the
historical `writing-practice-gap-v1` remains supported and frozen. Memory is
consulted only for exact maximum-gap ties in the fixed persistent-gap, trend,
planning-recency, and canonical-priority order. Phase 8 is COMPLETE after External Implementation Review approval: P8-03 through P8-12 are COMPLETE
and P8-13 is INTERNAL_AUDIT_COMPLETE. The bounded Writing-only Agent v1 and its
shared granular lifecycle compatibility are defined by
[docs/PHASE8_GRAPH.md](docs/PHASE8_GRAPH.md) and
[docs/CORE_LEARNING_AGENT_POLICY.md](docs/CORE_LEARNING_AGENT_POLICY.md).
The graph defines WHAT should be implemented.

The development loop defines HOW each graph node should be executed.

Do not implement functionality from future phases unless explicitly requested.

---

## 3. Required Reading

Before making significant changes, inspect:

1. `AGENTS.md`
2. `README.md`
3. current phase graph under `docs/`
4. `docs/DEVELOPMENT_LOOP.md`
5. relevant existing source files
6. existing tests

Do not assume the repository matches documentation.

Always inspect the actual implementation.

---

# 4. Technology Stack

Primary stack:

## Frontend

```text
Next.js
TypeScript
Tailwind CSS
```

## Backend

```text
Python
FastAPI
Pydantic v2
SQLAlchemy 2.x
Alembic
```

## Database

```text
PostgreSQL
```

## Testing

```text
pytest
httpx
```

## Infrastructure

```text
Docker
Docker Compose
```

Future technologies may include:

```text
pgvector
Redis
LangGraph
speech-to-text
text-to-speech
```

Do not introduce future technologies until there is a concrete requirement.

---

# 5. Architecture Principles

Prefer clear separation of responsibilities.

Expected backend architecture:

```text
app/
├── api/
├── core/
├── db/
├── models/
├── schemas/
├── services/
├── agent/
├── learner/
├── evaluators/
├── memory/
├── tools/
└── llm/
```

Not every directory needs to exist from the beginning.

Create modules only when they have an actual responsibility.

Avoid architecture for architecture's sake.

---

# 6. Agent Architecture Principles

The target architecture is:

```text
IELTS Learning Agent
        │
        ├── Learner Model
        ├── Planner
        ├── Memory
        ├── Evaluator
        ├── Reflection
        │
        └── Tools
             ├── Writing
             ├── Speaking
             ├── Reading
             └── Listening
```

Default to:

```text
one core agent
+
deterministic tools/services
```

Do NOT create multiple agents simply to make the architecture appear more agentic.

Introduce a sub-agent only when it needs:

* independent context,
* independent reasoning strategy,
* independent lifecycle,
* or clearly isolated responsibility.

---

# 7. LLM Usage Principles

LLMs should not control deterministic logic unnecessarily.

Prefer:

```text
Rules / Algorithms
+
LLM
```

Example:

```text
Algorithm decides WHAT should be trained.

LLM decides HOW the training content is generated.
```

Use structured outputs whenever LLM results enter application logic.

Prefer:

```text
LLM
↓
structured JSON
↓
Pydantic validation
↓
application logic
```

Avoid parsing arbitrary natural-language responses when structured data is appropriate.

Never treat LLM output as automatically valid.

---

# 8. Learner State Principles

Learner state must be structured and persisted.

Do not use the prompt itself as the source of truth for learner state.

Important learner information should eventually live in PostgreSQL.

Examples:

```text
goal score
current estimated score
skill mastery
weaknesses
practice history
task completion
```

Keep transient conversation context separate from persistent learner state.

---

# 9. Memory Principles

Do not treat all information as one generic memory blob.

Future memory architecture may distinguish:

```text
Profile Memory
Learning / Episodic Memory
Semantic Learning Memory
```

Do not introduce vector storage until semantic retrieval is actually required.

PostgreSQL is the default persistence layer.

---

# 10. Backend Coding Rules

Use modern Python.

Target:

```text
Python 3.12+
```

Prefer:

```python
list[str]
dict[str, Any]
str | None
```

over unnecessary legacy typing syntax.

Use type hints for public functions and important internal functions.

Prefer small functions with explicit responsibilities.

Avoid:

* giant service files,
* hidden global state,
* circular imports,
* premature abstraction,
* unnecessary inheritance.

---

# 11. FastAPI Rules

Keep API routes thin.

Preferred flow:

```text
API Router
↓
Service / Domain Logic
↓
Database / Agent / External Provider
```

Do not place complex business logic directly inside route handlers.

Use dependencies for:

```text
database sessions
configuration
future authentication
```

Return explicit schemas where practical.

---

# 12. Pydantic Rules

Use Pydantic v2 patterns.

Schemas represent API and domain boundaries.

Add validation for meaningful domain constraints.

For IELTS band values:

```text
minimum: 0
maximum: 9
valid increments: 0.5
```

Examples:

```text
5.0 valid
5.5 valid
6.0 valid

5.3 invalid
9.5 invalid
```

Avoid mutable defaults.

Prefer:

```python
Field(default_factory=list)
```

when necessary.

---

# 13. SQLAlchemy Rules

Use SQLAlchemy 2.x style.

Prefer:

```python
Mapped
mapped_column
```

Avoid deprecated SQLAlchemy 1.x patterns.

Keep models focused on persistence.

Do not mix large amounts of business logic into ORM models.

Use explicit foreign keys and relationships.

Think about extensibility before adding fixed columns for repeatable concepts.

Example:

Prefer:

```text
skill_name
mastery_score
```

over:

```text
task_response_score
coherence_score
grammar_score
...
```

when the concept should be extensible.

---

# 14. Database Migration Rules

All persistent schema changes must use Alembic.

Never manually change production-style database schemas without migrations.

Every migration should support:

```text
upgrade
downgrade
```

when reasonably possible.

After schema changes, validate migrations.

---

# 15. Configuration Rules

Use environment variables for environment-specific configuration.

Never hardcode:

* passwords,
* API keys,
* database credentials,
* production URLs,
* private tokens.

Maintain:

```text
.env.example
```

Never commit:

```text
.env
```

---

# 16. Testing Rules

Changes should be tested at the smallest useful level.

Typical commands:

```bash
pytest
```

For relevant changes also validate:

```text
application import
FastAPI startup
database connection
Alembic migrations
Docker configuration
```

Do not ignore failing tests.

Failure process:

```text
Reproduce
→ Find root cause
→ Make minimal fix
→ Run targeted test
→ Run relevant full tests
```

---

# 17. Development Loop

Every implementation task should follow:

```text
Observe
↓
Select
↓
Plan
↓
Implement
↓
Test
↓
Review
↓
Fix
↓
Commit
↓
Repeat
```

See:

```text
docs/DEVELOPMENT_LOOP.md
```

for detailed execution instructions.

---

# 18. Scope Control

Do not introduce technology or features only because they are fashionable.

Every new dependency must solve a concrete problem.

In particular, do not add these without a clear requirement:

```text
LangChain
LangGraph
Redis
Celery
Kafka
Milvus
Qdrant
Elasticsearch
Kubernetes
Multi-Agent architecture
Fine-tuning
Microservices
```

The project should remain as simple as possible while satisfying current requirements.

---

# 19. Git Workflow

Before modifying the repository:

```bash
git status
git branch
git log --oneline -5
```

Inspect existing changes before editing.

Do not overwrite unrelated user changes.

Before committing:

```bash
git diff
```

Review the actual changes.

Prefer small logical commits.

Examples:

```text
chore: initialize backend structure
feat: configure database persistence
feat: add learner domain models
feat: add writing evaluation schemas
test: add health endpoint tests
docs: update development setup
```

Do not combine unrelated changes in one commit.

Do not push unless explicitly requested.

---

# 20. Repository Safety

Never commit:

```text
.env
API keys
tokens
passwords
private credentials
__pycache__
local database files
unnecessary generated files
```

Do not delete or rewrite user work unless required for the current task.

Avoid destructive Git operations unless explicitly requested.

---

# 21. Documentation

Documentation must reflect the real implementation.

Do not claim that a feature exists if it has not been implemented.

When architecture, setup, commands, or behavior changes materially, update relevant documentation.

Keep `README.md` focused on users and developers.

Keep detailed development orchestration under:

```text
docs/
```

---

# 22. Decision Priority

When making engineering tradeoffs, prioritize:

```text
Correctness
>
Simplicity
>
Testability
>
Maintainability
>
Extensibility
>
Feature Count
```

Prefer a small correct implementation over a large speculative architecture.

---

# 23. Phase Boundary

When the current phase graph is complete:

STOP.

Do not automatically start the next phase.

Report:

```text
completed nodes
tests
migrations
Docker status
Git commits
known limitations
recommended next phase
```

Wait for explicit instruction before starting the next development phase.
