import assert from "node:assert/strict";
import test from "node:test";
import { ApiRequestError } from "../src/lib/api/client.ts";
import { isSubmissionConflictLocked, presentApiError, presentNoPracticeReasons, presentPracticeReasons, skillLabels } from "../src/lib/presentation.ts";

test("Chinese skill and planner presentation is centralized", () => { assert.equal(skillLabels.task_response, "任务回应（Task Response）"); assert.equal(presentNoPracticeReasons(["target_achieved"]), "你已达到当前目标分数，暂不需要生成针对性练习。"); assert.match(presentPracticeReasons(["largest_target_gap", "insufficient_evidence"]), /建议优先训练/); assert.doesNotMatch(presentPracticeReasons(["largest_target_gap"]), /暂不建议/); });
test("safe API errors distinguish stable codes and hide server text", () => { const cases: [string, string][] = [["request_invalid","请检查填写内容后重试。"],["provider_timeout","评估服务响应较慢，请稍后重试。"],["provider_rate_limited","评估服务当前繁忙，请稍后重试。"],["provider_unavailable","评估服务暂时不可用，请稍后重试。"],["persistence_unavailable","学习数据暂时无法保存或读取，请稍后重试。"]]; for(const [code, copy] of cases) assert.equal(presentApiError(new ApiRequestError(503,{code,message:"raw secret",fields:[]})),copy); assert.equal(presentApiError(new Error("secret")), "操作暂时无法完成，请稍后重试。"); });
test("conflict locks the normal submission and completion transition", () => {
  assert.equal(isSubmissionConflictLocked("conflict"), true);
  assert.equal(isSubmissionConflictLocked("submitted"), false);
});