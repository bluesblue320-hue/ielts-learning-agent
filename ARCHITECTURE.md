# IELTS Learning Agent Architecture

## 1. Architecture Goal

IELTS Learning Agent is designed as a long-term adaptive learning system rather than a simple IELTS chatbot.

The core learning loop is:

```text
Goal
  ↓
Observe Learner State
  ↓
Plan
  ↓
Practice
  ↓
Evaluate
  ↓
Update Learner State
  ↓
Store Learning Memory
  ↓
Replan
  ↺
```

The architecture should support this loop while remaining simple, testable, and extensible.

---

# 2. Core Design Principle

The system follows:

```text
One Core Learning Agent
+
Structured Learner State
+
Deterministic Services
+
Specialized Learning Tools
```

The initial architecture should NOT use a large multi-agent system.

Preferred:

```text
IELTS Learning Agent
        │
        ├── Planner
        ├── Learner Model
        ├── Memory
        ├── Evaluator
        └── Tools
```

Avoid:

```text
Planner Agent
Memory Agent
Writing Agent
Reading Agent
Listening Agent
Speaking Agent
Manager Agent
Reviewer Agent
```

unless future requirements justify independent agents.

---

# 3. High-Level Architecture

```text
                   ┌──────────────────────┐
                   │       Frontend       │
                   │ Next.js + TypeScript │
                   └──────────┬───────────┘
                              │
                         REST / SSE
                              │
                              ▼
                   ┌──────────────────────┐
                   │       FastAPI        │
                   │     API Layer        │
                   └──────────┬───────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │ IELTS Learning Runtime │
                  └────────────┬───────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
      Planner            Learner Model          Memory
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                               ▼
                         Tool Router
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
          Writing           Speaking          Future
            Tool              Tool            Tools
             │                 │
             └─────────────────┼─────────────────┐
                               ▼
                           Evaluator
                               │
                               ▼
                     Update Learner State
                               │
                               ▼
                            Replan
```

---

# 4. Frontend Layer

Technology:

```text
Next.js
TypeScript
Tailwind CSS
```

Responsibilities:

* display today's learning plan,
* provide practice interfaces,
* show writing results,
* show learner progress,
* show weaknesses and learning history,
* communicate with backend APIs.

The frontend must not contain core learning logic.

Example:

```text
frontend
   ↓
GET /plan/today
   ↓
backend decides plan
```

Do NOT calculate learning priorities in the frontend.

---

# 5. API Layer

Technology:

```text
FastAPI
Pydantic
```

Responsibilities:

* validate requests,
* expose backend functionality,
* return typed responses,
* manage HTTP concerns,
* call application services.

Preferred flow:

```text
API Route
   ↓
Service
   ↓
Domain / Agent Logic
   ↓
Database / LLM
```

Avoid:

```text
API Route
   ↓
500 lines of business logic
```

Routes should remain thin.

---

# 6. Learner Model

The Learner Model represents the system's structured understanding of the student.

Example:

```text
LearnerState
│
├── Goal
│   ├── target overall score
│   ├── target writing score
│   └── exam date
│
├── Current Level
│
├── Skill Mastery
│
├── Weaknesses
│
├── Practice History
│
└── Progress
```

Example skill state:

```text
Writing

Task Response       5.5
Coherence           6.0
Lexical Resource    6.0
Grammar             5.5
```

Learner state must be persisted in structured form.

The LLM prompt is NOT the source of truth.

Primary persistence:

```text
PostgreSQL
```

---

# 7. Skill Model

IELTS ability should eventually be represented at a finer level than four overall scores.

Example:

```text
Writing
│
├── Task Response
├── Idea Development
├── Argument Development
├── Coherence
├── Lexical Resource
├── Grammar
└── Article Usage
```

Each skill may eventually contain:

```text
skill_name
mastery_score
attempt_count
confidence
last_practiced_at
```

Use extensible skill records rather than creating database columns for every future skill.

---

# 8. Planner

The Planner decides what the learner should practice next.

Planner design should combine:

```text
Deterministic Logic
+
LLM Generation
```

The deterministic layer determines priorities.

Example:

```text
target Writing = 6.5
current Writing = 5.5

Task Response = 5.3
Grammar = 5.7
Coherence = 6.1

↓

Priority

Task Response       HIGH
Grammar             MEDIUM
Coherence           LOW
```

The LLM may then generate an appropriate task based on the selected priority.

Principle:

```text
Algorithm decides WHAT.

LLM helps decide HOW.
```

Avoid asking the LLM to control the entire learning strategy without constraints.

---

# 9. Learning Tools

Tools perform concrete learning activities.

Target tools:

```text
Writing Tool
Speaking Tool
Reading Tool
Listening Tool
Vocabulary Tool
Knowledge Retrieval Tool
```

Tools should expose clear interfaces.

Example:

```text
generate_writing_task()

evaluate_writing()

generate_grammar_drill()

generate_argument_drill()
```

The core runtime should not need to know internal implementation details.

---

# 10. Writing Pipeline

Writing is the first MVP learning domain.

Target flow:

```text
Writing Task
    ↓
Student Essay
    ↓
Writing Evaluator
    ↓
Structured Evaluation
    ↓
Update Learner Skills
    ↓
Save Attempt
    ↓
Create Learning Memory
    ↓
Planner
    ↓
Next Training Task
```

Evaluation output should be structured.

Example:

```json
{
  "overall_band": 5.5,
  "task_response": 5.5,
  "coherence": 6.0,
  "lexical_resource": 6.0,
  "grammar": 5.5,
  "weaknesses": [
    "idea_development",
    "article_usage"
  ],
  "error_tags": [
    "weak_argument",
    "article_error"
  ],
  "recommended_skills": [
    "idea_development",
    "article_usage"
  ]
}
```

---

# 11. Evaluator

Evaluator converts learning outcomes into structured evidence.

Example:

```text
Essay
  ↓
LLM Evaluation
  ↓
Structured JSON
  ↓
Pydantic Validation
  ↓
Application Logic
```

Never directly trust unvalidated LLM output.

Evaluation results may update:

```text
estimated score
skill mastery
weaknesses
learning memory
future plans
```

Evaluation and planning should remain separate responsibilities.

---

# 12. Memory Architecture

The future architecture distinguishes three conceptual memory types.

## Profile Memory

Stable learner information.

Examples:

```text
target score
exam date
available study time
learning preferences
```

## Episodic Learning Memory

Individual learning events.

Examples:

```text
completed Task 2
score 5.5
article errors
argument development weakness
```

## Semantic Learning Memory

Patterns derived from multiple learning events.

Example:

```text
Article errors appeared in four of the last five essays.
```

Phase 1 does not require vector memory.

Default storage:

```text
PostgreSQL
```

Vector retrieval should only be introduced when semantic retrieval becomes necessary.

---

# 13. LLM Layer

LLM access should be abstracted behind a provider interface.

Target:

```text
Application
    ↓
LLM Service
    ↓
Provider
```

Possible providers:

```text
DeepSeek
OpenAI
future providers
```

Application logic should not be tightly coupled to one model vendor.

Prefer structured generation for:

```text
evaluation
task generation
reflection
memory summarization
```

---

# 14. Persistence Layer

Primary database:

```text
PostgreSQL
```

Initial entities:

```text
users

learner_profiles

learner_skills

writing_attempts

writing_evaluations

learning_memories

study_plans

learning_tasks
```

Phase 1 may implement only a subset required by the current graph.

Database evolution must use Alembic migrations.

---

# 15. Agent Runtime

The Learning Agent runtime coordinates the system.

Future conceptual loop:

```text
load learner
     ↓
load relevant context
     ↓
planner
     ↓
select task
     ↓
execute learning activity
     ↓
evaluate
     ↓
update learner state
     ↓
store memory
     ↓
check replanning condition
     ↓
continue / stop
```

Initial implementation should use plain Python.

Do not introduce LangGraph until graph complexity makes explicit state-machine orchestration useful.

---

# 16. State vs Memory

These concepts must remain distinct.

## State

Represents the learner now.

Example:

```text
Writing = 5.7
Task Response = 5.4
Grammar = 5.8
```

## Memory

Represents what happened before.

Example:

```text
2026-08-12:
Task 2 essay scored 5.5.
Main weakness was argument development.
```

Planner may use both:

```text
Current State
+
Relevant Memory
+
Goal
↓
Next Action
```

---

# 17. Current MVP Boundary

The initial MVP focuses on:

```text
Writing
+
Learner State
+
Structured Evaluation
+
Learning Memory
+
Planner
```

Target MVP loop:

```text
Set Writing Goal
      ↓
Complete Task 2
      ↓
Evaluate
      ↓
Update Learner State
      ↓
Store Memory
      ↓
Generate Next Training
```

This loop is more important than feature count.

---

# 18. Phase Evolution

## Phase 1 — Foundation

```text
FastAPI
PostgreSQL
SQLAlchemy
Alembic
Pydantic
Docker
core schemas
```

## Phase 2 — Writing Evaluation

```text
LLM Provider
Writing Evaluator
Structured Output
Writing Submission Pipeline
```

## Phase 3 — Learning Loop

```text
Learner State Update
Memory
Planner
Next-task generation
```

## Phase 4 — Speaking

```text
Speech Input
Speaking Evaluation
Speaking Skill Model
```

## Phase 5 — Reading and Listening

```text
Objective Scoring
Error Classification
Adaptive Practice
```

## Future

Possible additions:

```text
pgvector
RAG
Redis
LangGraph
advanced knowledge tracing
adaptive difficulty
multi-agent specialization
```

Only introduce them when justified by concrete requirements.

---

# 19. Architecture Priorities

Engineering decisions should prioritize:

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

The architecture should evolve from real product requirements rather than speculative complexity.
