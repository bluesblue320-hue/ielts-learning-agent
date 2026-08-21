import type { AgentOutcome, AgentTool, AgentTurnResponse } from "@/lib/api/client";

export const agentStopLabels: Record<AgentTurnResponse["stop_reason"], string> = {
  needs_initial_writing: "请先完成首次写作。",
  needs_practice_submission: "请提交本次练习作文。",
  practice_ready: "下一份针对性练习已准备好。",
  await_submission: "本次提交正在处理中，请稍后刷新后继续。",
  target_achieved: "你已达到当前目标分数，暂不需要新的练习。",
  no_practice: "当前没有可继续的针对性练习。",
  submission_conflict: "这份作文与已提交内容不一致，请核对后重试。",
  max_actions: "本轮已完成安全操作上限，请再次点击继续学习。",
};

const toolLabels: Record<AgentTool, string> = {
  observe: "读取学习状态",
  generate_practice: "生成针对性练习",
  submit_practice: "提交练习作文",
  complete_practice: "完成练习并更新建议",
};

const outcomeLabels: Record<AgentOutcome, string> = {
  observation_classified: "已确认当前状态",
  practice_generated: "已生成练习",
  practice_resolved: "已恢复已有练习",
  generation_stale_discarded: "状态已变化，未保存过期练习",
  submission_submitted: "已提交并完成评估",
  submission_reused: "已恢复已提交的评估",
  submission_in_progress: "提交仍在处理中",
  submission_conflict: "提交内容不一致",
  completion_applied: "已更新学习状态",
  completion_reused: "已恢复已有学习更新",
};

export function presentAgentStopReason(
  stopReason: AgentTurnResponse["stop_reason"],
): string {
  return agentStopLabels[stopReason];
}

export function presentAgentStep(tool: AgentTool, outcome: AgentOutcome): string {
  return `${toolLabels[tool]}：${outcomeLabels[outcome]}`;
}