import assert from "node:assert/strict";
import test from "node:test";

import {
  wikiKnowledgeMetadata,
  wikiNeighborLabels,
  wikiSourceLocation,
} from "../src/lib/wiki-presentation.ts";
import type {
  KnowledgeAuthority,
  WikiKnowledgeProjection,
  WikiSourceProjection,
  WritingTask2TaskType,
} from "../src/lib/api/client.ts";

const backendAuthorities: KnowledgeAuthority[] = [
  "official_ielts",
  "official_british_council",
  "official_idp",
];
const representativeTaskType: WritingTask2TaskType = "cause_solution";
// @ts-expect-error arbitrary strings are outside the frozen backend enum
const invalidTaskType: WritingTask2TaskType = "arbitrary_task_type";
void invalidTaskType;

test("Wiki source presentation preserves locator, page, and section", () => {
  assert.equal(
    wikiSourceLocation({
      source_id: "source",
      authority: "official_ielts",
      publisher: "IELTS",
      title: "Descriptors",
      url: "https://ielts.org/example",
      source_type: "official_web_or_pdf",
      verified_at: "2026-08-21",
      source_revision: null,
      locator: "Task Response",
      page: 3,
      section: "Band 7",
    }),
    "Task Response · 第 3 页 · Band 7",
  );
});

test("Wiki client types cover the full closed backend enum contracts", () => {
  const alternativeSource: WikiSourceProjection = {
    source_id: "source",
    authority: "official_british_council",
    publisher: "British Council",
    title: "Writing guidance",
    url: "https://example.test/writing",
    source_type: "official_web_or_pdf",
    verified_at: "2026-08-21",
    source_revision: null,
    locator: "Task types",
    page: null,
    section: null,
  };
  const taskTypeProjection: WikiKnowledgeProjection = {
    knowledge_id: "writing-task2-type-cause-solution",
    knowledge_version: "ielts-writing-knowledge-v1",
    task: "writing_task2",
    category: "task_understanding",
    statement: "A canonical task-type statement.",
    criterion: null,
    descriptor_band: null,
    task_type: representativeTaskType,
    sources: [alternativeSource],
  };

  assert.deepEqual(backendAuthorities, [
    "official_ielts",
    "official_british_council",
    "official_idp",
  ]);
  assert.equal(taskTypeProjection.task_type, "cause_solution");
  assert.equal(taskTypeProjection.sources[0].authority, "official_british_council");
});

test("Wiki detail metadata remains descriptive and deterministic", () => {
  assert.deepEqual(
    wikiKnowledgeMetadata({
      criterion: "task_response",
      descriptor_band: 7,
      task_type: null,
    }),
    ["评分维度：task_response", "描述档位：Band 7"],
  );
});

test("adjacent-band labels do not imply a learning recommendation", () => {
  assert.equal(wikiNeighborLabels.previous_band, "查看上一档评分描述");
  assert.equal(wikiNeighborLabels.next_band, "查看下一档评分描述");
  assert.doesNotMatch(
    `${wikiNeighborLabels.previous_band}${wikiNeighborLabels.next_band}`,
    /推荐|课程|必修|提升路径/,
  );
});
