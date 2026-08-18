import assert from "node:assert/strict";
import test from "node:test";

import {
  readLearnerPresentationCache,
  writeLearnerPresentationCache,
} from "../src/lib/learner-cache.ts";

function createStorage() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
    values,
  };
}

test("the learner cache persists only the approved presentation fields", () => {
  const storage = createStorage();
  writeLearnerPresentationCache(storage, {
    currentLearnerId: 4,
    writingTargetBand: "7.0",
    currentRecommendationId: 9,
    currentRecommendation: { decision_type: "no_practice" } as never,
  });

  const raw = [...storage.values.values()][0];
  assert.deepEqual(Object.keys(JSON.parse(raw)).sort(), [
    "currentLearnerId",
    "currentRecommendation",
    "currentRecommendationId",
    "writingTargetBand",
  ]);
  assert.equal(readLearnerPresentationCache(storage)?.currentLearnerId, 4);
});

test("the learner cache rejects an invalid browser value", () => {
  const storage = createStorage();
  storage.setItem("ielts-learning-agent.phase5.presentation", "{invalid");
  assert.equal(readLearnerPresentationCache(storage), null);
});
