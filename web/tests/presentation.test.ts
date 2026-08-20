import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { ApiRequestError } from "../src/lib/api/client.ts";
import { isSubmissionConflictLocked, presentApiError, presentNoPracticeReasons, presentPlanningExplanation, presentPracticeReasons, skillLabels } from "../src/lib/presentation.ts";
import { progressSourceLinkLabel } from "../src/lib/memory-presentation.ts";

test("Chinese skill and planner presentation is centralized", () => { assert.equal(skillLabels.task_response, "任务回应（Task Response）"); assert.equal(presentNoPracticeReasons(["target_achieved"]), "你已达到当前目标分数，暂不需要生成针对性练习。"); assert.match(presentPracticeReasons(["largest_target_gap", "insufficient_evidence"]), /建议优先训练/); assert.doesNotMatch(presentPracticeReasons(["largest_target_gap"]), /暂不建议/); });
test("safe API errors distinguish stable codes and hide server text", () => { const cases: [string, string][] = [["request_invalid","请检查填写内容后重试。"],["provider_timeout","评估服务响应较慢，请稍后重试。"],["provider_rate_limited","评估服务当前繁忙，请稍后重试。"],["provider_unavailable","评估服务暂时不可用，请稍后重试。"],["persistence_unavailable","学习数据暂时无法保存或读取，请稍后重试。"]]; for(const [code, copy] of cases) assert.equal(presentApiError(new ApiRequestError(503,{code,message:"raw secret",fields:[]})),copy); assert.equal(presentApiError(new Error("secret")), "操作暂时无法完成，请稍后重试。"); });
test("conflict locks the normal submission and completion transition", () => {
  assert.equal(isSubmissionConflictLocked("conflict"), true);
  assert.equal(isSubmissionConflictLocked("submitted"), false);
});
test("dashboard practice generation delegates errors to the centralized mapping", () => { const source = readFileSync(new URL("../src/app/dashboard/page.tsx", import.meta.url), "utf8"); assert.match(source, /catch \(reason\) \{\s*setError\(presentApiError\(reason\)\);/); });

test("progress drill-down labels are ordinal, not raw database ids", () => {
  assert.equal(progressSourceLinkLabel(0), "查看来源记录 1");
  assert.equal(progressSourceLinkLabel(2), "查看来源记录 3");
  // The progress page must not render raw episode ids in visible link copy.
  const source = readFileSync(new URL("../src/app/progress/page.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(source, /查看学习记录 #/);
  assert.match(source, /progressSourceLinkLabel\(index\)/);
});

test("P7 explanation copy is deterministic, Chinese-first, and safely versioned", () => {
  assert.equal(
    presentPlanningExplanation({
      planner_version: "writing-practice-gap-memory-v2",
      planning_explanation: {
        factors: ["equal_maximum_target_gap", "trend_tiebreak"],
      },
    } as never),
    "当前多个能力与目标分差距相同。同等薄弱项中，系统根据近期表现趋势优先选择了这一项。",
  );
  assert.equal(
    presentPlanningExplanation({
      planner_version: "writing-practice-gap-v1",
    } as never),
    null,
  );
  assert.equal(
    presentPlanningExplanation({
      planner_version: "writing-practice-gap-memory-v2",
      planning_explanation: null,
    } as never),
    null,
  );
  assert.equal(
    presentPlanningExplanation({
      planner_version: "writing-practice-gap-memory-v2",
      planning_explanation: { factors: ["unexpected_factor"] },
    } as never),
    "系统已根据当前学习状态生成下一步建议。",
  );
});

test("P7 explanation views render safe copy without raw audit provenance", () => {
  const dashboard = readFileSync(new URL("../src/app/dashboard/page.tsx", import.meta.url), "utf8");
  const detail = readFileSync(new URL("../src/app/history/[episodeId]/page.tsx", import.meta.url), "utf8");
  for (const source of [dashboard, detail]) {
    assert.match(source, /presentPlanningExplanation/);
    assert.match(source, /推荐依据/);
    assert.doesNotMatch(source, /planner_context_snapshot|source_observation_ids|source_episode_ids|selection_trace/);
  }
});
