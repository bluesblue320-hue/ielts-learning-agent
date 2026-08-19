import type {
  EpisodeType,
  ResumeAction,
  TrendStatus,
} from "./api/client.ts";

// Phase 6 memory presentation mapping (Chinese-first). These labels are
// learner-facing copy only; the backend remains authoritative for semantics.

export const episodeTypeLabels: Record<EpisodeType, string> = {
  initial_writing: "首次写作",
  targeted_practice: "针对性练习",
};

export const trendLabels: Record<TrendStatus, string> = {
  improving: "提升中",
  stable: "稳定",
  declining: "下滑中",
  insufficient_history: "证据不足",
};

export const trendExplanations: Record<TrendStatus, string> = {
  improving: "最近三次评估呈上升趋势。",
  stable: "最近三次评估保持稳定。",
  declining: "最近三次评估呈下降趋势。",
  insufficient_history: "至少需要三次评估才能判断趋势。",
};

export const persistentGapLabels = {
  established: "低于目标分数",
  insufficient_history: "证据不足",
} as const;

export const resumeActionLabels: Record<ResumeAction, string> = {
  initial_writing: "开始首次写作",
  no_action: "当前目标已达成",
  generate_practice: "生成针对性练习",
  submit_practice: "继续完成练习",
  await_submission: "练习提交处理中",
  complete_practice: "完成练习并获取下一步建议",
};

export const resumeActionExplanations: Record<ResumeAction, string> = {
  initial_writing: "还没有学习记录，请完成首次 Writing Task 2 写作。",
  no_action: "系统暂时没有建议的下一步练习。",
  generate_practice: "系统已准备好针对性练习，可以开始生成。",
  submit_practice: "有一项已生成的练习等待完成。",
  await_submission: "上一次提交仍在处理中，请稍后刷新查看。",
  complete_practice: "练习已提交，可以完成练习并获取下一步建议。",
};

export function formatEpisodeTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
