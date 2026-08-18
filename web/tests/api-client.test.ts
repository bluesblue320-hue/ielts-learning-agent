import assert from "node:assert/strict";
import test from "node:test";

import { ApiRequestError, createApiClient } from "../src/lib/api/client.ts";

test("the client sends the published apply handoff request", async () => {
  let requestedUrl = "";
  let requestedInit: RequestInit | undefined;
  const client = createApiClient({
    baseUrl: "http://api.example.test/",
    fetch: async (url, init) => {
      requestedUrl = String(url);
      requestedInit = init;
      return Response.json({
        learning_update_id: 7,
        reused: false,
        recommendation_id: 11,
        recommendation: {},
      });
    },
  });

  const result = await client.applyEvaluation(3, 5);

  assert.equal(requestedUrl, "http://api.example.test/learners/3/writing/evaluations/5/apply");
  assert.equal(requestedInit?.method, "POST");
  assert.equal(result.recommendation_id, 11);
});

test("the client preserves the safe backend error envelope", async () => {
  const client = createApiClient({
    baseUrl: "http://api.example.test",
    fetch: async () => Response.json(
      { error: { code: "practice_conflict", message: "Practice is not submitted.", fields: [] } },
      { status: 409 },
    ),
  });

  await assert.rejects(
    () => client.getPracticeEvaluation(3, 5),
    (error: unknown) =>
      error instanceof ApiRequestError &&
      error.status === 409 &&
      error.code === "practice_conflict" &&
      error.message === "Practice is not submitted.",
  );
});
