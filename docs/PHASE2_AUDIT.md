# Phase 2 Final Audit

## Scope and decision

This record audits the authorized Phase 2 Writing Evaluation Pipeline against
[PHASE2_GRAPH.md](PHASE2_GRAPH.md). The implemented path accepts a Task 2
question and essay, obtains a structured provider result through a typed
provider boundary, validates it, computes the product band deterministically,
and atomically persists the attempt and evaluation before returning the API
response.

Local, PostgreSQL, migration, and Docker gates passed on 2026-08-13
after the final review hardening. The final pull request's GitHub Actions
status is the authoritative
external CI gate; Phase 2 is accepted only when that status is green. After
acceptance, execution stops at `P2-15`. No Phase 3 work is authorized by this
record.

## Node evidence

| Node | Result | Commit |
| --- | --- | --- |
| P2-01 Baseline and CI | Deterministic PostgreSQL-backed CI established | `1b5a00a3b0847847e8bfa91f21791ee45d8ead69` |
| P2-02 Writing schemas | Strict typed boundaries, word count, and scoring policy | `c9f3f09ac096944afcb7108293209b4b902dbdb9` |
| P2-03 Persistence models | Writing attempt/evaluation SQLAlchemy models | `2ae4a206f233b0e469bbe1424ff3176be7901ab7` |
| P2-04 Migration | Reversible `0002_writing` revision | `6915d48170ac39828712ad1c7d13981c859ffbda` |
| P2-05 Provider contract | Vendor-independent protocol, errors, and test fake | `f27f1371e00475ab7607f5cadaaf6a69c1e3d344` |
| P2-06 DeepSeek adapter | Environment-only configuration and validated HTTP adapter | `34c68b1e360e858a0a46bc1d0f33fcaf7a2c278c` |
| P2-07 Evaluator | Trusted request construction and deterministic aggregation | `0f469cfea2e921b6717b9d5a0333fe984277bd18` |
| P2-08 Persistence service | Atomic write and rollback behavior | `8e7a6fb11ed16442ee992c8ed76e73735795b245` |
| P2-09 API | Thin `POST /writing/evaluate` route and production wiring | `02f182491ffdd9309645c6c7df49d8b8b95cb8ef` |
| P2-10 Failures/retries | Stable API mapping and bounded transient retries | `d03c38b1dad0af85da6fc79c213c7f73ecb252a5` |
| P2-11 Automated suite | Deterministic provider/network safety coverage | `d0b22f2f4775591889ab047901b0ffef03fd6362` |
| P2-12 Integration | PostgreSQL isolation, success, invalid-output, and rollback flows | `f3a4ff8105901a7a000281b9c990e2577681cddd` |
| P2-13 Docker | Runtime/test image and Compose validation | `687ba13b9d6dce2a6ed156c62c82f3da03186834` |
| P2-14 Documentation | README, local workflow, API, and architecture synchronized | `4e6b18da8781bddde8fcb3abfae5ccb3a0d5c8cd` |
| P2-15 Final audit | This record; the commit SHA is reported with the final PR evidence | This commit |

## Validation evidence

- Deterministic non-integration command: 342 passed, 41 integration tests
  deselected, with no database URL or DeepSeek key.
- Focused schema/rubric/provider/retry suite: 197 passed.
- Focused PostgreSQL migration/persistence/API/integration suite: 39 passed.
- Complete local suite against the isolated PostgreSQL test database: 383
  passed.
- Complete container suite against an isolated Compose test database: 383
  passed.
- One Alembic head: `0002_writing`.
- Explicit isolated migration cycle: `0002_writing` downgraded to
  `0001_phase1` (Writing tables absent), then upgraded to `0002_writing`
  (both Writing tables present).
- The separate development sentinel table and marker remained unchanged, and
  no Alembic table appeared in that sentinel database.
- Fake-provider API/integration tests cover successful persisted responses,
  invalid structured output with zero writes, commit failure with rollback,
  and health behavior without a live provider.

One upstream `StarletteDeprecationWarning` is emitted by FastAPI's current
`TestClient` import path. It does not fail or skip tests.

## Provider, scoring, and failure boundaries

- Application services depend on `LLMProvider`, not `DeepSeekProvider`.
- Production composition builds only the DeepSeek adapter; `FakeProvider` is a
  test-only injection seam and cannot be selected by ordinary runtime settings.
- Request validation caps questions at 2,000 characters and essays at 20,000
  characters before provider or database work.
- Evaluator requests carry the versioned `writing-task2-v1` definitions, band
  anchors, task-length guidance, scoring policy, and output schema; provider
  payloads cannot set application-owned metadata.
- Provider output is Pydantic-validated before aggregation or persistence.
- Word count and the equal-weight four-criterion product band are deterministic;
  exact quarter-band ties round upward to the nearest half band.
- Provider calls make at most three total attempts and retry only normalized
  timeout, rate-limit, or transient failures.
- Retry delays increase deterministically from 0.25 to 0.5 seconds through an
  injected async sleeper; account/billing failures are never retried.
- DeepSeek thinking mode defaults explicitly to `disabled`, is sent on every
  request using `thinking.type`, and is persisted as application metadata.
- Safe API errors do not expose submitted content, raw provider bodies,
  credentials, vendor request identifiers, or database exception details.
- Attempt and evaluation writes use one transaction; failure cannot leave a
  partial successful record or produce a success response.

## Docker and security evidence

- `docker compose config`, runtime/test image builds, database/API health, and
  migration completion passed from a clean ASCII-path checkout.
- The migration job upgraded an empty development database through
  `0001_phase1` to `0002_writing`.
- A production-composed request without a key returned `503`
  `provider_configuration`, with zero attempt/evaluation rows; it did not return
  a fake evaluation.
- The runtime image contains no `/app/tests` tree, and runtime/test image
  metadata contains no provider key, token, or secret variable.
- The rendered Compose provider key was empty during validation; no live
  DeepSeek call or credential was required.
- Relative Markdown links, tracked and working-tree high-confidence secret
  patterns, forbidden runtime paths/dependencies, and whitespace checks passed.
- The final Compose project, named volume, and temporary validation worktree
  were removed after validation.

## Known limitations

- No live DeepSeek smoke test was performed, so real-account availability,
  model entitlement, latency, and output quality are not certified by Phase 2.
- FakeProvider adversarial tests verify the application trust boundary, request
  construction, structured-output validation, and safe handling of untrusted
  question/essay content. They do not prove a real LLM cannot be prompt-injected;
  perfect prompt-injection prevention is not claimed.
- The computed product band is an application policy and is not claimed to be
  exactly equivalent to an official final IELTS Writing band.
- Phase 2 does not update learner state, store learning memory, plan tasks, run
  an agent loop, use RAG, provide a frontend, or implement Speaking, Reading, or
  Listening workflows.

## Next-phase recommendation and stop

The next phase should begin with a separately reviewed and explicitly authorized
graph. A reasonable first design target is a minimal structured learner-state
boundary that can consume persisted Writing evaluation evidence without putting
state or planning decisions inside prompts. No such functionality is implemented
or authorized here.

When the final pull request CI is green, all Phase 2 acceptance gates are
satisfied and the executor must stop. Do not begin Phase 3 automatically.
