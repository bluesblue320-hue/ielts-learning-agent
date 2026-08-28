# Development Loop

## Purpose

This document defines **how** to execute each node from the current authorized
phase graph. It does not authorize a phase, start phase execution, or activate a
node by itself. Apply the loop only after the current phase and its graph have
been explicitly authorized for execution.

```text
Observe
  -> Select
  -> Plan
  -> Implement
  -> Test
  -> Review
  -> Fix if needed
  -> Commit
  -> Repeat
```

## Phase Execution Loop

### Purpose

The Phase Execution Loop defines how an authorized phase may be executed
continuously across multiple graph nodes.

It does not authorize a phase by itself.

Phase execution may begin only when:

1. the phase graph exists;
2. the phase has been explicitly authorized for execution;
3. at least one node is `READY`.

Once continuous phase execution is explicitly authorized, the executor may
continue selecting and executing `READY` nodes without requiring new user
authorization after every completed node.

The executor must stop only when:

- the graph reaches its declared `STOP` condition;
- execution enters an unrecoverable `BLOCKED` state;
- explicit execution authority is revoked;
- continuing would require work outside the authorized phase.

### Phase loop

```text
START
  ↓
Observe phase state
  ↓
Re-read authorized graph
  ↓
Phase complete?
  ├── YES → Final validation → Report → STOP
  │
  └── NO
       ↓
Select READY node
       ↓
Execute Node Loop
       ↓
Node accepted?
  ├── NO → FIXING
  │        ↓
  │      Fix
  │        ↓
  │      Revalidate
  │        └───────────────┐
  │                        │
  └── YES                  │
       ↓                   │
Mark COMPLETE              │
       ↓                   │
Commit checkpoint          │
       ↓                   │
Record evidence            │
       ↓                   │
Re-read graph ─────────────┘
```

## Serial Batch Between Gates

A graph or explicit authorization may define a batch of consecutive `READY`
nodes. Within an authorized batch, keep one node `ACTIVE` at a time: finish,
test, review, and fix the current node; mark it `COMPLETE`; select the next
valid `READY` node; and continue automatically.

Never execute nodes in parallel, skip dependencies, cross an explicit review or
approval gate, or continue after a stop condition. Default selection remains the
lowest-numbered `READY` node unless the user explicitly chooses another valid
node.

Explicit gates include at minimum External Design Review, Milestone Review,
External Implementation Review, and PR / merge authorization. A gate is a hard
stop: a later node may not start until the required external or human approval
is recorded in the graph. Repository-safety rules, frozen-contract boundaries,
and all other stop conditions remain unchanged.

## 1. Observe

Establish the repository's actual state before editing:

```bash
git status
git branch
git log --oneline -5
```

Then read `AGENTS.md`, `README.md`, the current phase graph, this development loop, relevant source files, and existing tests. Confirm whether documented commands and files really exist. Note unrelated user changes and protect them.

Observation must answer:

- What is currently implemented?
- Which graph nodes are complete, ready, active, or blocked?
- What changed since the documentation was written?
- Which constraints, failures, or user changes affect the next action?

## 2. Select

Choose exactly one `READY` node from the current authorized phase graph, and keep
at most one node `ACTIVE` at a time. Selection is deterministic:

1. If the user explicitly selects a `READY` node, use that node.
2. Otherwise, when multiple nodes are `READY`, select the lowest-numbered one.
3. Before activation, confirm every declared dependency is `COMPLETE` and the
   node belongs to the current authorized phase.

Never select a downstream node whose dependencies are incomplete or route around
a failure. If an explicitly requested node is not `READY`, report why and do not
activate it. Do not combine future functionality with current-phase work. If no
node is ready or phase execution has not been authorized, stop and report that
state.

## 3. Plan

Define a minimal node plan before editing:

- intended outcome and acceptance condition;
- files expected to change;
- smallest useful implementation steps;
- targeted and full validation commands;
- external services or configuration required;
- known risks and explicit non-goals.

Revise the plan if inspection disproves an assumption. Do not add frameworks, abstractions, directories, or dependencies that the selected node does not require.

## 4. Implement

Make the smallest coherent change that satisfies the selected node. Keep API routes thin, configuration typed, persistence explicit, and responsibilities separated. Preserve unrelated changes and never write secrets or `.env` files into Git.

Implementation stays inside the selected node. Discovering useful later work is not permission to perform it; record it as a limitation or follow-up.

## 5. Test

Run validation at the smallest useful level first, followed by the node's relevant full checks.

Typical progression:

```text
static/import check
  -> targeted unit or API test
  -> relevant pytest suite
  -> database/migration check when affected
  -> Docker validation when affected
```

Use isolated test configuration and databases. Tests must not depend on personal credentials, mutate production-like data, or hide external-service failures. A skipped required check is not a passing check; document why it could not run and treat the node as incomplete or blocked.

## 6. Review

Inspect the actual change before deciding it is complete:

```bash
git diff
git status
```

Review for:

- correctness against the node acceptance condition;
- unintended or unrelated changes;
- scope creep and forbidden capabilities;
- secret exposure and unsafe defaults;
- missing error handling or tests;
- deprecated library patterns;
- documentation that overstates the implementation;
- broken links, commands, migrations, or Docker configuration.

## 7. Fix if needed

Any failed test or review finding routes back to the same node:

```text
Reproduce
  -> identify root cause
  -> make the minimal fix
  -> rerun targeted validation
  -> rerun relevant full validation
  -> review again
```

Do not weaken assertions, delete valid tests, suppress errors, or expand scope merely to obtain a passing result. If the root cause belongs to an incomplete dependency, pause the node and repair that dependency through the graph. If user input or new authority is required, mark the node blocked and report the exact need.

## 8. Commit

Commit only after the node's required validations pass and the diff contains only the logical unit being completed.

Git rules:

- stage explicit related paths rather than all repository changes;
- inspect the staged diff and run `git diff --cached --check`;
- use a concise conventional message such as `feat: add health endpoints` or `test: cover database readiness`;
- never commit `.env`, credentials, local databases, caches, or unrelated generated files;
- do not amend, rewrite, reset, or delete user history without explicit instruction;
- do not push unless explicitly requested.

If a commit cannot be created, retain the validated work, report the blocker, and do not mark the node complete.

## 9. Repeat

Record the completed node, validation evidence, commit, and known limitations. Re-read the dependency graph and identify newly ready nodes.

Repeat only when continued phase execution is authorized. When the current
phase's acceptance criteria are complete, follow its graph's stop condition:
report results and wait. Never start the next phase automatically; a new phase
requires separate explicit authorization and its own authorized graph.

## Failure summary

| Failure type | Route |
| --- | --- |
| Implementation or test failure | Keep the current node active; reproduce, fix, and revalidate |
| Migration or database failure | Stop dependent work; validate configuration and migration state in isolation |
| Docker failure | Preserve logs, fix the smallest configuration issue, rebuild, and recheck health |
| Scope conflict | Reject the out-of-scope change and request an explicit graph or phase decision |
| Missing user input or authority | Mark the node blocked and state exactly what is required |
| Unrelated dirty worktree changes | Preserve them; stage and commit only selected paths |
| Potential secret exposure | Stop, remove the secret from the change safely, and assess whether rotation is required |

Successful execution means both the implementation and its evidence are trustworthy. Passing tests alone do not override scope, documentation, or repository-safety requirements.
