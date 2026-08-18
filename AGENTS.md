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
Phase 4 — Adaptive Writing Practice
```

Read:

```text
docs/PHASE4_GRAPH.md
docs/DEVELOPMENT_LOOP.md
```

The Phase 3 graph is approved and its runtime nodes have been executed:
learner-state policy and schemas, persistence models and migration, evidence
extraction, the deterministic EWMA replay engine, the practice planner, the
atomic learning-application service, learner/learning APIs, and concurrency
hardening are implemented and validated against isolated PostgreSQL. Phase 3
is complete; see [docs/PHASE3_GRAPH.md](docs/PHASE3_GRAPH.md) for the per-node
status and [docs/PHASE3_AUDIT.md](docs/PHASE3_AUDIT.md) for the final audit.

Phase 4 implements the bounded adaptive Writing loop on its dedicated branch:
a Phase 3 recommendation is resolved to at most one durable practice, an
essay-only submission is evaluated against the stored question, and the
persisted evaluation is applied through Phase 3 to return the next
recommendation. Phase 4 execution is pending its final internal audit and
external review; Phase 5 must not start.

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
