import assert from "node:assert/strict";
import test from "node:test";
import { ApiRequestError } from "../src/lib/api/client.ts";
import { presentApiError, presentPlannerReasons, skillLabels } from "../src/lib/presentation.ts";

test("Chinese skill and planner presentation is centralized", () => { assert.equal(skillLabels.task_response, "任务回应（Task Response）"); assert.equal(presentPlannerReasons(["target_achieved"]), "你已达到当前目标分数，暂不需要生成针对性练习。"); });
test("safe API errors never expose server messages", () => { const error = new ApiRequestError(503, { code: "persistence_unavailable", message: "raw SQL", fields: [] }); assert.equal(presentApiError(error), "学习数据暂时无法保存或读取，请稍后重试。"); assert.equal(presentApiError(new Error("secret")), "操作暂时无法完成，请稍后重试。"); });