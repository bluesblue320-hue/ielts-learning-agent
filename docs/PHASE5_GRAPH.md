# Phase 5 Graph — Chinese-first Web Product MVP

## Document status

**COMPLETE AND MERGED — P5-01 through P5-15 complete; P5-16 internal audit complete; External Review approved; PR #9 merged.**

This graph is frozen on `phase/5-web-product-mvp`, created from `master` at
`6aef28490d918905553c8c2335fd1d3c406bd7b9` (`Merge pull request #8 from
bluesblue320-hue/phase/4-adaptive-writing-practice`). The working tree was clean before the branch was created. P5-01 and P5-02 were completed as the design baseline; P5-03 through P5-15 were subsequently executed on this frozen graph, followed by the P5-16 internal audit. External Review approved the completed graph, and PR #9 (`feat: deliver Phase 5 Chinese-first web MVP`) merged it to `master` at `56498c3d59aad4ae645c5b78c6b6dc41bec62bcf`.

Phase 4 is the accepted implementation baseline. Its Phase 2 evaluation,
Phase 3 learner-state/planning, and Phase 4 practice lifecycle policies remain
authoritative and unchanged.

---

## 1. Goal and architecture

A Simplified-Chinese IELTS learner must be able to use the browser alone to
complete one bounded adaptive Writing loop:

```text
Create learner
  -> set target band
  -> submit initial Task 2
  -> view evaluation
  -> apply learning update
  -> view learner state and recommendation
  -> generate targeted practice
  -> complete practice essay
  -> submit and view evaluation
  -> update learner state
  -> receive next recommendation
  -> STOP / HUMAN TIME
```

```text
Next.js + TypeScript + Tailwind  -- HTTP / JSON -->  FastAPI
                                                     |       |
                                                PostgreSQL  DeepSeek
```

Frozen ownership:

- **Next.js:** presentation layer only.
- **FastAPI:** application and domain layer.
- **PostgreSQL:** source of truth.
- **DeepSeek:** bounded AI capability.

Next.js MUST NOT become a second business backend. Evaluation, learner state,
planner, practice, persistence, and business policy remain in FastAPI. Next.js
API routes, Route Handlers, and Server Actions MUST NOT contain business logic;
a transport-only proxy/rewrite may be considered later only if justified.

---

## 2. Dependency graph

```text
P5-01 Baseline & API Capability Audit [COMPLETE]
  -> P5-02 Web Product Contract Freeze [COMPLETE]
       -> P5-03 Next.js Foundation [COMPLETE]
       -> P5-04 Backend Web Compatibility [COMPLETE]
P5-03 + P5-04 [COMPLETE] -> P5-05 Typed API Client [COMPLETE] -> P5-06 App Shell + Learner Context [COMPLETE]
P5-06 -> P5-07 Dashboard [COMPLETE]
P5-06 -> P5-08 Initial Writing UX [COMPLETE]
P5-07 + P5-08 -> P5-09 Evaluation + Apply UX [COMPLETE] -> P5-10 Recommendation + Practice Generation [COMPLETE]
  -> P5-11 Practice Workspace [COMPLETE] -> P5-12 Submission Feedback [COMPLETE] -> P5-13 Complete + Replan UX [COMPLETE]
  -> P5-14 UX Resilience / Responsive / Accessibility [COMPLETE]
  -> P5-15 Browser E2E + CI + Production Build [COMPLETE]
  -> P5-16 Internal Final Audit [INTERNAL_AUDIT_COMPLETE] -> External Review [APPROVED] -> PR #9 [MERGED] -> STOP
```

All declared dependencies were satisfied in order. P5-01 through P5-15 are COMPLETE; P5-16 is INTERNAL_AUDIT_COMPLETE; External Review is APPROVED; PR #9 is MERGED; Phase 5 is COMPLETE.

---

## 3. P5-01 — Baseline & API Capability Audit — COMPLETE

**Authority:** read-only audit of `master` at the verified Phase 4 merge
baseline. **Deliverable:** the audited UI contract and gaps in
`WEB_PRODUCT_CONTRACT.md`.

### Findings

| Required capability | Current public API | Web status |
| --- | --- | --- |
| Create learner and target | `POST /learners` | Available |
| View four-skill state | `GET /learners/{learner_id}/state` | Available |
| Submit initial Task 2 | `POST /writing/evaluate` | Evaluation display available; apply handoff incomplete |
| Apply initial evaluation | `POST /learners/{learner_id}/writing/evaluations/{evaluation_id}/apply` | Blocked by missing public initial `evaluation_id`; its response also lacks `recommendation_id` |
| Resolve recommendation | `POST /learners/{learner_id}/writing/recommendations/{recommendation_id}/practice` | Blocked until apply exposes the persisted recommendation identity |
| Inspect practice | `GET /learners/{learner_id}/writing/practices/{practice_id}` | Available |
| Submit practice | `POST /learners/{learner_id}/writing/practices/{practice_id}/submit` | Submission outcome available; full evaluation retrieval absent |
| Complete and replan | `POST /learners/{learner_id}/writing/practices/{practice_id}/complete` | Replans, but its next recommendation cannot be resolved later because no public next recommendation ID is returned |

Confirmed gaps:

1. `POST /writing/evaluate` persists both identifiers internally but returns
   `attempt_id` and the evaluation body only. Its public response does **not**
   return the distinct persisted `evaluation_id` that the apply endpoint
   requires. The frontend MUST NOT infer that two independent database IDs are
   equal.
2. `LearningApplyResponse` returns the pure planner decision but not its
   persisted `recommendation_id`. The generation endpoint is recommendation
   scoped, so the browser has no legal identity with which to resolve the
   returned decision. The ID belongs beside, not inside,
   `PracticeRecommendationDecision`.
3. `ClosedLoopResult` returns `next_recommendation` but not its persisted
   `next_recommendation_id`. A future `practice` decision returned by complete
   consequently cannot be resolved through the existing recommendation-scoped
   generation endpoint.
4. Practice submission returns `status`, `attempt_id`, and `evaluation_id` for
   `submitted`/`reused`, but there is no public endpoint to retrieve the full
   persisted evaluation for that practice. `GET /practices/{practice_id}`
   exposes lifecycle and `attempt_id`, not evaluation content.

These were API compatibility gaps, not defects in evaluation, learner-state, planner, practice, or persistence policy. They were resolved by the additive P5-04 implementation without redesigning those policies.

---

## 4. P5-02 — Web Product Contract Freeze — COMPLETE

**Authority:** freeze the first MVP routes, browser journey, presentation
states, Chinese-first language policy, and stable error-code mapping. The
complete contract is `WEB_PRODUCT_CONTRACT.md`.

The frontend presents authoritative persisted content as returned. It does not
rewrite planner semantics, calculate bands, translate persisted LLM feedback,
or reveal backend identifiers to learners.

---

## 5. Executed node boundaries

### P5-03 — Next.js Foundation

Initialize only `web/` with Next.js, TypeScript, Tailwind CSS, App Router, and
npm. Prefer a small dependency set. Do not add Redux, Zustand, React Query,
large UI frameworks, or complex Server Actions architecture by default.

### P5-04 — Backend Web Compatibility

May make only small additive FastAPI changes required by the frozen web
contract. The required candidates discovered in P5-01 are:

- expose the persisted `evaluation_id` in the successful initial-evaluation
  handoff (prefer an additive field on `POST /writing/evaluate`);
- expose `recommendation_id` beside the existing pure `recommendation` on
  `LearningApplyResponse` from `POST .../evaluations/{evaluation_id}/apply`;
- expose `next_recommendation_id` beside the existing pure
  `next_recommendation` on `ClosedLoopResult` from `POST .../complete`;
- add `GET /learners/{learner_id}/writing/practices/{practice_id}/evaluation`
  to expose the persisted evaluation linked through `Practice -> Attempt ->
  Evaluation`.

The practice-evaluation endpoint, if implemented, must enforce learner
ownership, require a submitted practice, use the authoritative attempt link,
and return safe 4xx/5xx failures. These four changes are additive API/
application-result compatibility only. P5-04 MUST NOT redesign evaluation
policy, scoring, learner state, planner, the Phase 4 lifecycle, or persistence
models.

### P5-05 through P5-15

Implement only in dependency order: typed API client; shell/context; dashboard
and initial-writing UX; evaluation/apply UX; recommendation/generation;
practice workspace; submission feedback; completion/replan; resilience;
browser E2E, CI, and production build.

P5-15 quality gates are:

```text
python -m pytest -q --strict-markers
npm run lint
npm run typecheck
npm run test
npm run build
```

Browser E2E uses Playwright + Next.js + FastAPI + deterministic
`FakeProvider`/`FakePracticeGenerator` + real isolated PostgreSQL. It MUST
prove the full browser loop and MUST NOT call DeepSeek in CI.

### P5-16 — Internal Final Audit — INTERNAL_AUDIT_COMPLETE

Executed final state:

```text
P5-01..P5-15 = COMPLETE
P5-16 = INTERNAL_AUDIT_COMPLETE
External Review = APPROVED
PR #9 = MERGED
Phase 5 = COMPLETE
STOP
Phase 6 = NOT_STARTED
```

---

## 6. Scope and stop condition

Out of scope: authentication; payments; Reading, Listening, and Speaking;
RAG/vector storage/semantic memory; LangGraph or multi-agent runtime; Redis,
Celery, Kafka; admin/social/leaderboard features; full i18n or English UI
mode; and production cloud deployment, Kubernetes, or microservices.

Final stop condition: `P5-01..P5-15 = COMPLETE`; `P5-16 = INTERNAL_AUDIT_COMPLETE`; `External Review = APPROVED`; `PR #9 = MERGED`; `Phase 5 = COMPLETE`; `STOP`. Phase 6 remains NOT_STARTED.

External-review findings were routed back to their owning completed nodes for targeted repair and revalidation, then returned to external review for approval. The dependency graph and node set remain unchanged.
