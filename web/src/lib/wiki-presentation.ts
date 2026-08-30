import type {
  WikiNeighborDirection,
  WikiPageType,
  WikiSourceProjection,
} from "./api/client.ts";

export const wikiPageTypeLabels: Record<WikiPageType, string> = {
  root: "知识首页",
  section: "知识分类",
  criterion: "评分维度",
  band_descriptor: "分数档描述",
  task_rule: "写作规则",
  task_type: "题型",
};

export const wikiNeighborLabels: Record<WikiNeighborDirection, string> = {
  parent: "返回上一级",
  child: "查看下一级",
  previous_band: "查看上一档评分描述",
  next_band: "查看下一档评分描述",
};

export function wikiSourceLocation(source: WikiSourceProjection): string {
  return [
    source.locator,
    source.page === null ? null : `第 ${source.page} 页`,
    source.section === null ? null : source.section,
  ]
    .filter((value): value is string => value !== null)
    .join(" · ");
}

export function wikiKnowledgeMetadata(input: {
  criterion: string | null;
  descriptor_band: number | null;
  task_type: string | null;
}): string[] {
  const metadata: string[] = [];
  if (input.criterion !== null) metadata.push(`评分维度：${input.criterion}`);
  if (input.descriptor_band !== null) metadata.push(`描述档位：Band ${input.descriptor_band}`);
  if (input.task_type !== null) metadata.push(`题型：${input.task_type}`);
  return metadata;
}
