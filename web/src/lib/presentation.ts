import { ApiRequestError, type PlanningExplanationFactor, type PracticeRecommendation, type WritingSkill } from "./api/client.ts";

export const skillLabels: Record<WritingSkill, string> = {
  task_response: "任务回应（Task Response）",
  coherence_and_cohesion: "连贯与衔接（Coherence and Cohesion）",
  lexical_resource: "词汇资源（Lexical Resource）",
  grammatical_range_and_accuracy: "语法多样性与准确性（Grammatical Range and Accuracy）",
};

const errorCopy: Record<string, string> = {
  request_invalid: "请检查填写内容后重试。",
  provider_timeout: "评估服务响应较慢，请稍后重试。",
  provider_rate_limited: "评估服务当前繁忙，请稍后重试。",
  provider_unavailable: "评估服务暂时不可用，请稍后重试。",
  provider_invalid_response: "评估结果暂时不可用，请稍后重试。",
  provider_request_rejected: "评估请求暂时无法处理，请稍后重试。",
  provider_configuration: "学习服务暂时不可用，请稍后重试。",
  provider_authentication: "学习服务暂时不可用，请稍后重试。",
  provider_billing_unavailable: "学习服务暂时不可用，请稍后重试。",
  persistence_unavailable: "学习数据暂时无法保存或读取，请稍后重试。",
  learner_not_found: "未找到当前学习者，请重新设置学习目标。",
  evaluation_not_found: "未找到这次评估，请重新提交或刷新页面。",
  practice_not_found: "未找到这项练习，请返回学习概览。",
  practice_conflict: "该练习当前状态不允许此操作，请刷新后重试。",
  episode_not_found: "未找到这条学习记录，请返回写作历史。",
};

export function presentApiError(error: unknown): string {
  if (error instanceof ApiRequestError) return errorCopy[error.code] ?? "操作暂时无法完成，请稍后重试。";
  return "操作暂时无法完成，请稍后重试。";
}

export function presentNoPracticeReasons(reasonCodes: string[]): string {
  const primary = reasonCodes[0];
  return ({
    target_achieved: "你已达到当前目标分数，暂不需要生成针对性练习。",
    cold_start: "系统需要更多写作证据，完成首次评估后会提供建议。",
    incomplete_state: "学习状态尚未完整建立，请先完成当前必要步骤。",
    target_unset: "请先设置 Writing 目标分数。",
  } as Record<string, string>)[primary] ?? "系统暂不建议生成针对性练习。";
}

export function presentPracticeReasons(reasonCodes: string[]): string {
  const copy: Record<string, string> = {
    largest_target_gap: "当前能力与目标分数差距最大，建议优先训练这一项。",
    priority_tiebreak: "多个能力项差距相同时，系统按固定优先级选择了这一项。",
    insufficient_evidence: "当前证据仍较少，本次训练也会帮助进一步校准学习状态。",
  };
  return reasonCodes.filter((code) => copy[code]).map((code) => copy[code]).join(" ");
}
const planningExplanationCopy: Record<PlanningExplanationFactor, string> = {
  equal_maximum_target_gap: "当前多个能力与目标分差距相同。",
  persistent_gap_tiebreak: "该能力近期持续低于目标，因此优先练习。",
  trend_tiebreak: "同等薄弱项中，系统根据近期表现趋势优先选择了这一项。",
  lower_recent_practice_count: "同等薄弱项中，该能力最近练习次数更少。",
  canonical_priority_tiebreak: "同等薄弱项仍无法区分，系统按固定优先级选择了这一项。",
};

export function presentPlanningExplanation(
  recommendation: PracticeRecommendation | null | undefined,
): string | null {
  if (
    recommendation?.planner_version !== "writing-practice-gap-memory-v2" ||
    recommendation.planning_explanation === null
  ) {
    return null;
  }

  const copy = recommendation.planning_explanation.factors
    .map((factor) => planningExplanationCopy[factor])
    .filter((message): message is string => message !== undefined);
  return copy.length > 0
    ? copy.join("")
    : "系统已根据当前学习状态生成下一步建议。";
}

export function isSubmissionConflictLocked(status: string | null): boolean {
  return status === "conflict";
}