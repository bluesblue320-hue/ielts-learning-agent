import assert from "node:assert/strict";
import test from "node:test";

import { presentAgentStep, presentAgentStopReason } from "../src/lib/agent-presentation.ts";

test("Agent presentation is Chinese-first and exposes only safe tool outcomes", () => {
  assert.equal(
    presentAgentStopReason("needs_practice_submission"),
    "请提交本次练习作文。",
  );
  assert.equal(
    presentAgentStep("submit_practice", "submission_reused"),
    "提交练习作文：已恢复已提交的评估",
  );
  assert.equal(
    presentAgentStep("complete_practice", "completion_reused"),
    "完成练习并更新建议：已恢复已有学习更新",
  );
});