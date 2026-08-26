# Phase 10 Evaluation Surface Audit

## Status

**P10-01 - Existing Evaluation Surface Audit: COMPLETE. P10-01 External Review: APPROVED.** This is a
repository-backed, documentation-only audit. It adds no Eval implementation,
corpus, labels, API, migration, CI change, dependency, or production behavior
change. The scope is frozen Writing Task 2 and writing-task2-v1.

Required Phase 8-10 graphs/audits and Knowledge, Agent, Memory, Planner, and
State policies were read before code inspection. Actual source/tests are the
evidence.

## Evidence matrix and confidence rule

**Implementation existence != coverage.** A property is
`ALREADY_COVERED_DETERMINISTICALLY` only when a stable existing test or
equivalent repository evidence directly proves it. Evidence inferred across
several local tests, rather than one cross-layer contract, is
`PARTIALLY_COVERED`.

| Surface | Property | Implementation evidence | Test evidence | Classification | Gap / Phase 10 implication |
| --- | --- | --- | --- | --- | --- |
| Scoring | Application owns request/rubric/prompt/metadata | `app/services/writing_evaluation.py`; `app/llm/provider.py`; `app/evaluators/rubrics/writing_task2_v1.py` | `tests/test_writing_evaluator.py::test_evaluator_owns_provider_and_prompt_metadata`; `tests/test_llm_provider_contract.py::test_request_boundary_is_strict_and_separates_trusted_content` | ALREADY_COVERED_DETERMINISTICALLY | Reuse frozen request fixtures. |
| Scoring | Provider cannot override product band | `app/schemas/writing.py::aggregate_product_band` | `tests/test_writing_evaluator.py::test_evaluator_rejects_provider_product_band_override` | ALREADY_COVERED_DETERMINISTICALLY | Contract case. |
| Provider | Invalid structured response fails closed | `app/llm/deepseek.py`; `app/services/writing_evaluation.py` | `tests/test_llm_provider_contract.py::test_fake_provider_normalizes_invalid_structured_output_safely`; `tests/test_deepseek_provider.py::test_deepseek_missing_or_invalid_fields_fail_structured_validation` | ALREADY_COVERED_DETERMINISTICALLY | Fake/captured malformed cases. |
| Retry | Bounded retry and no write after exhaustion | `app/llm/retry.py`; `app/api/routes/writing.py` | `tests/test_llm_retry.py::test_transient_category_retries_then_succeeds_without_mutating_request`; `tests/test_writing_api.py::test_retryable_failure_stops_at_three_attempts_without_write` | ALREADY_COVERED_DETERMINISTICALLY | Provider-boundary case. |
| Lifecycle | Atomic persistence, idempotency, ownership | `app/services/writing_persistence.py`; `app/services/learning_application.py`; `app/models/learning.py` | `tests/test_writing_persistence.py::test_commit_failure_rolls_back_flushed_pair`; `tests/test_learning_application.py::test_idempotent_replay_returns_existing_without_duplicate_effects`; `tests/test_learning_application.py::test_cross_owner_reuse_is_explicit_conflict` | ALREADY_COVERED_DETERMINISTICALLY | Reuse isolated PostgreSQL. |
| State | Decimal/half-band canonical replay | `app/learner/state_engine.py`; `app/learner/writing_evidence.py` | `tests/test_state_engine.py::test_ewma_exact_intermediates_never_rounded`; `tests/test_state_engine.py::test_late_older_evidence_rebuilds_to_canonical_order`; `tests/test_writing_state_policy.py` | ALREADY_COVERED_DETERMINISTICALLY | Provider-free replay. |
| Memory/Planner | Provenance, profile, exact-tie/reconstruction | `app/memory/episode_queries.py`; `app/memory/atoms.py`; `app/memory/profile.py`; `app/learner/memory_planner.py` | `tests/test_memory_queries.py::test_episode_detail_full_provenance`; `tests/test_memory_atoms.py::test_practice_completed_after_submit_and_apply`; `tests/test_memory_profile.py::test_traceability_and_determinism`; `tests/test_memory_planner.py::test_recent_practice_then_canonical_priority_have_frozen_semantics`; `tests/test_memory_planner_reconstruction.py::test_valid_exact_tie_snapshot_reconstructs_after_semantic_replay`; `tests/test_planner.py::test_tie_break_priority_order_is_frozen` | ALREADY_COVERED_DETERMINISTICALLY | Promote precise outcomes later. |
| Practice | Ownership, freshness, replay, grounding | `app/services/practice_generation.py`; `app/services/practice_submission.py`; `app/services/practice_completion.py` | `tests/test_practice_generation.py::test_cross_learner_request_is_rejected_before_generator_call`; `tests/test_practice_submission.py::test_same_fingerprint_reuses_result_without_second_provider_call`; `tests/test_phase9_practice_grounding.py::test_shared_generation_service_builds_grounded_v2_request` | ALREADY_COVERED_DETERMINISTICALLY | Structure/authority are in scope. |
| Knowledge | IDs/locators/retrieval/citations | `app/knowledge/writing_task2_v1.py`; `app/knowledge/retriever.py`; `app/knowledge/rubric_compatibility.py`; `app/services/writing_guidance.py` | `tests/test_knowledge_snapshot.py::test_official_snapshot_has_stable_unique_ids_and_resolving_provenance`; `tests/test_knowledge_retriever.py::test_retrieval_is_deterministic_bounded_and_deduplicated`; `tests/test_rubric_knowledge_compatibility.py::test_all_reviewed_knowledge_references_resolve_and_align`; `tests/test_phase9_grounding_hardening.py::test_public_guidance_claims_and_citations_resolve_to_snapshot`; `tests/test_guidance_api.py::test_guidance_api_returns_grounded_practice_guidance_without_provider` | ALREADY_COVERED_DETERMINISTICALLY | Authority cross-layer case. |
| Agent | Structured trajectory/bounds/stale handling | `app/agent/executor.py`; `app/agent/selector.py`; `app/agent/observation.py`; `app/agent/tools.py`; `app/schemas/agent.py` | `tests/test_agent_executor.py::test_turn_never_exceeds_frozen_mutation_provider_or_observation_bounds`; `tests/test_agent_selector.py::test_old_generated_practice_is_rejected_before_evaluation`; `tests/test_agent_observation.py::test_no_updates_needs_initial_writing_without_provider`; `tests/test_agent_tools.py::test_tools_delegate_directly_to_existing_services`; `tests/test_agent_api.py::test_agent_stale_generated_first_submission_is_safe_conflict`; `tests/test_agent_schemas.py::test_public_response_is_strict_and_contains_no_internal_trace_fields` | ALREADY_COVERED_DETERMINISTICALLY | Use AgentTurnResponse, not free text. |
| Full lifecycle | Evaluation -> update -> State -> Memory -> Planner -> Practice -> Agent | Service boundaries above | Separate Phase 2-9 tests, no canonical one-case proof | PARTIALLY_COVERED / REQUIRES_TRACE_OR_EVIDENCE_EXPOSURE | Test-side evaluator/report needed, not production tracing. |
## Scoring and provider boundary

POST /writing/evaluate validates WritingSubmission, injects LLMProvider, calls
WritingEvaluationService, then persists atomically. The request builder owns
rubric/prompt versions, criterion definitions, descriptors, half-band and
length guidance, word count, scoring policy, output schema, metadata, and
safety constraints. The question/essay are untrusted. ProviderEvaluationPayload
owns qualitative criterion bands/evidence/feedback only.

aggregate_product_band deterministically uses four validated half-bands, equal
weights, and Decimal half-up rounding; provider output cannot override the
product band. Evaluator/provider tests cover invalid bands, metadata/product
override, malformed payload, HTTP/timeouts/network/JSON/missing-fields,
normalized failure, and bounded retry (maximum three attempts).

FakeProvider records scripted payloads/errors, FakePracticeGenerator supplies
policy-valid content, and tests/conftest.py prevents live provider HTTP. These
are reusable for deterministic regression, not proof of live score stability.

## Durable lifecycle and planning evidence

WritingSubmission -> WritingEvaluationResult -> WritingAttempt/WritingEvaluation
-> LearningUpdate + 4 LearningEvidence + 4 LearnerSkillState
-> PracticeRecommendation

WritingEvaluationPersistenceService validates before write and rolls back.
apply_writing_evaluation locks learner ownership, uses unique
LearningUpdate.writing_evaluation_id for idempotency, reuses same-owner results,
rejects cross-owner use, rebuilds durable state, and has no provider call in its
transaction. Persistence, application, concurrency, and Phase 3 tests prove
row accounting, rollback, idempotency, conflict, and canonical replay.

test_state_engine.py proves writing-state-ewma-v1 exact Decimal arithmetic,
half-band handling, created-at/id chronology, late-arrival rebuild, and
repeatability. app/memory and its query/atom/profile/API tests prove L0/L1/L2/L3
source identity, learner isolation, trend/gap/recency, and read-only/provider-
free behavior. Planner and memory-planner tests prove v1/v2 terminal branches,
exact ties, and persistent gap -> trend -> recency -> canonical priority.

The full Evaluation -> apply -> State -> Memory -> v2 Planner path is
PARTIALLY_COVERED: its invariants are inferred across tests, but no current
canonical evaluator emits one mode-labelled verdict and first failing boundary.
Existing durable rows and response structures are sufficient test-side evidence;
no production instrumentation is proven necessary.

Chronology must stay purpose-specific: State uses WritingAttempt created_at ASC,
id ASC; Memory lists LearningUpdate created_at DESC, id DESC; Agent/guidance
current state uses LearningUpdate.id DESC.

## Practice, Knowledge, and Agent

Practice tests prove recommendation ownership, generation idempotency,
no-practice no-op, provider failure behavior, fingerprint replay/conflict,
claim recovery, stale fences, concurrency, and completion/replan. Completion is PARTIALLY_COVERED as a reusable Phase 10 trajectory. Generated-practice semantic or pedagogical quality is TOO_SUBJECTIVE_FOR_DETERMINISTIC_VERIFICATION and OUT_OF_SCOPE for Phase 10 Writing score calibration v1. Phase 10 may deterministically verify recommendation ownership, target skill/band, version compatibility, Knowledge IDs/grounding, freshness, provider failure, replay/idempotency, and schema structure, but must not create a human-rated practice-quality calibration corpus.

Phase 9 snapshot/retriever/descriptor/compatibility/grounding/guidance tests
prove Knowledge IDs/locators, bounded deterministic retrieval,
application-owned citations, injection rejection, and safe chronology. Knowledge
cannot redefine scoring or choose the Planner target. That complete
cross-layer authority proof is PARTIALLY_COVERED.

Agent executor bounds are: mutating tools 3, observations 4, provider-backed
calls 2, automatic generations 1, automatic completions 1. AgentTurnResponse
provides initial/final observations, closed AgentStep tool/outcome sequence,
stop_reason, recommendation, and practice. Agent schema/selector/observation/
executor/tools/API tests cover sequences, re-observation, replay, generation,
completion, conflicts, provider budget, ownership, and bounds. Trajectory Eval
must use this structured evidence plus durable freshness/chronology/ownership,
never free text or private reasoning.

## API, browser, fixtures, and CI

FastAPI tests cover Writing, learning, practice, Memory, guidance, and Agent.
Browser tests are product evidence, not automatic proof of all backend semantics:
closed-loop covers an adaptive loop; Phase 6 history/progress/resume; Phase 7
v1/v2 rendering; Phase 8 Agent continuation; Phase 9 citations after reload.

### CI capability and trigger distinction

`.github/workflows/ci.yml` has suitable **runtime capability** for a future deterministic gate: Ubuntu 24.04, Python 3.12, PostgreSQL 17, provider-free backend tests, web lint/typecheck/unit/build, and Playwright E2E. Its current `push.branches` list is exactly `master`, `phase/5-web-product-mvp`, and `phase/7-memory-aware-planning-v2`; the current Phase 10 branch is **NOT CONFIGURED** for push. A `pull_request` trigger is **AVAILABLE**. This audit has no evidence the P10-01 commit passed CI. P10-15 must decide integration; Live Calibration Mode must not gate merge.
## Historical regression candidates (not created)

| Candidate | Origin and historical failure | Exact current protection | Future regression use |
| --- | --- | --- | --- |
| Provider metadata/product-band override | `9565647 fix: harden writing provider evaluation boundary`: provider content must not claim application-owned product outcome or metadata. | `tests/test_writing_evaluator.py::test_evaluator_rejects_provider_product_band_override`; `tests/test_writing_evaluator.py::test_evaluator_rejects_provider_attempt_to_override_metadata` | Deterministic ownership case. |
| Retry/no-write-before-final-outcome | Phase 2 provider/API hardening: transient retry must not persist partial rows or exceed policy. | `tests/test_writing_api.py::test_retryable_failure_can_recover_to_one_atomic_success`; `tests/test_writing_api.py::test_retryable_failure_stops_at_three_attempts_without_write`; `tests/test_llm_retry.py::test_every_established_error_category_has_deterministic_retry_behavior` | Provider-boundary case. |
| Late arrival/concurrency canonical state | Phase 3 replay/concurrency work: arrival order must not become evidence semantics. | `tests/test_learning_concurrency.py::test_concurrent_equals_sequential_and_late_arrival`; `tests/test_state_engine.py::test_late_older_evidence_rebuilds_to_canonical_order`; `tests/test_phase3_consolidated.py::test_canonical_order_equivalence_across_schedules` | Chronology/replay case. |
| Planner v2 exact ties and v1/v2 reconstruction | Phase 7 policy/persistence: Memory resolves exact ties only and v1 history remains reconstructible. | `tests/test_memory_planner.py::test_recent_practice_then_canonical_priority_have_frozen_semantics`; `tests/test_memory_planner_application.py::test_exact_tie_apply_persists_internal_snapshot_and_replays_v2`; `tests/test_memory_planner_reconstruction.py::test_valid_exact_tie_snapshot_reconstructs_after_semantic_replay` | Outcome/trajectory case. |
| Claim recovery/fingerprint/stale practice | Phase 8 fixes `af00c4f`, `a046891`: differing essay or stale practice must not invoke provider work or fabricate success. | `tests/test_practice_submission.py::test_reclaimed_old_token_cannot_finalize`; `tests/test_practice_submission.py::test_agent_first_submission_freshness_fence_rejects_advanced_learner`; `tests/test_agent_api.py::test_agent_stale_generated_first_submission_is_safe_conflict` | Authority/fail-closed case. |
| Rubric-Knowledge compatibility/citations | Phase 9 hardening `58cf487`, `738b430`: ID existence alone cannot prove semantic compatibility or citation truth. | `tests/test_rubric_knowledge_compatibility.py::test_id_existence_alone_cannot_create_a_compatibility_result`; `tests/test_phase9_grounding_hardening.py::test_public_guidance_claims_and_citations_resolve_to_snapshot`; `tests/test_phase9_descriptor_semantics.py::test_every_descriptor_has_aligned_official_claim_provenance` | Knowledge-grounding case. |
## Required questions and recommendation

1. Existing tests enforce strict contracts, aggregation, retry/failure, rollback,
ownership/idempotency, Decimal state, Memory/Planner, practice lifecycle,
Knowledge/citations, and Agent bounds.
2. Missing: a canonical evaluator across provider fixture/capture, lifecycle,
State, Memory, Planner, grounded practice, and Agent response.
3. Existing observable evidence: WritingEvaluationResult, returned IDs,
LearningUpdate/evidence/state/recommendation rows, planner snapshot, Memory,
PracticeResponse, and AgentTurnResponse.
4. Minimum v1 needs no proven instrumentation; use test-side collection. P10-02
may permit only test-only non-semantic exposure if needed.
5. Deterministic alternatives: FakeProvider, FakePracticeGenerator, injected
HTTP, and the live-network guard.
6. Prompt/private-envelope/UI-copy tests can be implementation details unless a
frozen policy owns them; use structured/durable assertions.
7. The table lists historical candidates; no cases/labels are created.
8. No calibration corpus, raw labels, rater provenance/adjudication, agreement
metric, or captured live run exists.
9. Existing GitHub Actions Python/PostgreSQL CI can run deterministic regression.
10. Smallest v1: pytest-integrated cross-layer checks using existing fakes,
isolated PostgreSQL, AgentTurnResponse, and JSON/report artifacts.

Deterministic Regression Mode uses fake/captured payloads and existing structured
evidence. Live Calibration Mode needs real essays/provider scores plus
independent raw human/reference scores, provenance, disagreement/adjudication,
and agreement/bias/variance. Calibration Replay Mode recomputes reports from
captured outputs/labels without another provider call.

contract correctness != reference-score agreement
provider variance != code regression

### REUSE

- Existing pytest/CI PostgreSQL, fakes, network guard, migrations, factories,
  structured results, durable rows, Memory/Planner, Knowledge, and Agent response.

### NEED_NEW (after P10-02 freeze)

- Separate versioned regression-case/result and calibration/reference-label schemas.
- Test-side runner/evaluators, first-failure attribution, JSON/report artifacts.
- Calibration corpus with raw labels, provenance, disagreement/adjudication,
  captured provider metadata, and replay inputs.

### DO_NOT_BUILD

- Public Eval API/dashboard, production trace table, migration, generic framework,
  vector DB/RAG, LangChain/LangGraph, Redis/Celery/Kafka, or live-provider CI gate.
- Any scoring, rubric, Planner, Memory, Agent, or Knowledge semantic change.

P10-01 audit and its External Review are COMPLETE and APPROVED. P10-02 is the sole next READY design node. Formal External Design Review remains PENDING_P10-02; P10-03 and implementation remain unauthorized.
