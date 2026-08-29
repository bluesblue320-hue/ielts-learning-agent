import assert from "node:assert/strict";
import test from "node:test";

import {
  wikiKnowledgeMetadata,
  wikiNeighborLabels,
  wikiSourceLocation,
} from "../src/lib/wiki-presentation.ts";

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
