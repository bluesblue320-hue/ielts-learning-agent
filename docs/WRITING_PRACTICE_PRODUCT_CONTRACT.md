# Writing Practice Product Contract — Phase 4

**Version:** `writing-practice-product-v1` (frozen by `P4-02`)
**Status:** ACCEPTED — implementation authority for product semantics

This contract freezes exactly what Phase 4 means by Practice, Submission,
submission lifecycle, completion, and closed-loop result. It is the product
authority referenced by `docs/PHASE4_GRAPH.md` and consumed by the generation
policy (`docs/WRITING_PRACTICE_GENERATION_POLICY.md`), the Phase 4 schemas
(`P4-04`), and the Phase 4 services (`P4-09`/`P4-10`/`P4-11`).

---

## 1. Core lifecycle

```text
PracticeRecommendation (Phase 3)
  -> Practice (generated, persisted)
  -> HUMAN PRACTICE TIME (minutes/hours/days)
  -> Submission (learner essay for that practice)
  -> Evaluation (existing Phase 2, provider outside DB transaction)
  -> Apply (existing Phase 3 learner-state update)
  -> Replan (new PracticeRecommendation, exposed as closed-loop result)
```

## 2. Definitions

- **Practice**: one durable targeted IELTS Writing Task 2 practice generated
  for exactly one eligible `PracticeRecommendation` (`decision_type =
  practice`). A practice owns its authoritative generated question and all
  generated content.
- **Submission**: the learner's essay submitted for a specific persisted
  practice. Submission is **essay-oriented**: the input carries the essay
  only; the trusted question comes from the persisted practice.
- **Submission lifecycle**: `generated -> submission_in_progress ->
  submitted` (see section 4).
- **Completion (closed-loop result)**: the derived trace
  `practice -> WritingAttempt -> WritingEvaluation -> LearningUpdate -> next
  PracticeRecommendation`. There is no redundant `completed` flag.
- **Closed-loop result**: the persisted next `PracticeRecommendation`, which
  may be `practice` or `no_practice`; both are valid successful outcomes.

## 3. Decision-gated behavior (frozen)

- `decision_type = practice` — MAY generate exactly one targeted Writing
  practice (at most one durable `writing_practices` row per recommendation).
- `decision_type = no_practice` — MUST produce:
  - zero generator calls;
  - zero `writing_practices` rows;
  - a deterministic no-practice outcome based on the persisted Phase 3
    recommendation (reasons `cold_start`, `incomplete_state`,
    `target_achieved`, `target_unset` are Phase 3-owned and never
    reinterpreted).
- **Cold start** — Phase 4 does NOT implement bootstrap/diagnostic practice
  generation. A cold-start learner obtains Writing evidence through the
  already-existing submission/evaluation path before adaptive targeted
  practice is available:
  `cold_start -> no targeted Phase 4 practice -> no generator call -> no
  writing_practices row`.

## 4. Submission lifecycle states

| State | Meaning |
| --- | --- |
| `generated` | durable practice exists; no claim; `attempt_id` NULL |
| `submission_in_progress` | a claim is active (claim token + fingerprint); an evaluator may run; a second claim request returns a safe in-progress outcome |
| `submitted` | `WritingAttempt` + `WritingEvaluation` + `attempt_id` link atomically finalized; the practice cannot be re-submitted with a different essay |

## 5. Question authority (frozen)

- The practice owns the generated question.
- The learner submission API MUST NOT accept a client-controlled replacement
  question.
- The server constructs the existing Phase 2 `WritingSubmission` internally:

  ```text
  WritingSubmission(
      question=persisted_practice.question,   # authoritative
      essay=validated_user_essay,             # untrusted
  )
  ```

- The submission fingerprint is computed over the authoritative validated
  submission payload (conceptually practice identity + persisted question +
  validated essay; exact encoding is `P4-02`/`P4-04` implementation policy).
  The client cannot alter the question used for evaluation.

## 6. Submission claim protocol (semantics)

- Phase 4 allows exactly ONE logical submission per practice; the practice ID
  is the ownership/idempotency anchor.
- Same fingerprint after submission -> return the existing persisted
  attempt/evaluation result, no new provider call.
- Different fingerprint after submission -> explicit
  practice-already-submitted conflict, no provider call.
- During `submission_in_progress`, any incoming request -> stable safe
  in-progress/conflict outcome, NO additional evaluator call.
- No process-local mutex provides correctness.

## 7. Primary end-to-end acceptance story

Start from an ESTABLISHED learner state that already yields
`PracticeRecommendation: decision_type = practice, target_skill =
task_response` (example: learner target 7.0; TR 6.0, CC 6.5, LR 6.5,
GRA 6.5; Phase 3 recommends `task_response`):

```text
existing Phase 3 recommendation (practice, task_response)
  -> P4 generate targeted Task Response practice (persisted question)
  -> persist one writing_practices row
  -> human submission (learner submits ESSAY only; the practice question is
     authoritative and reused, never replaced by the client)
  -> claim submission (fingerprint + claim token)
  -> server constructs WritingSubmission(question from practice, essay from
     user) -> Fake/evaluation provider OUTSIDE DB transaction
  -> atomically persist WritingAttempt + WritingEvaluation + practice link
  -> existing Phase 3 apply
  -> new LearnerSkillState
  -> new PracticeRecommendation (practice OR no_practice; both valid)
```

The complete end-to-end test runs with fakes and isolated PostgreSQL. No live
DeepSeek.
