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

test("the client fetches the Phase 6 memory read contracts as GETs", async () => {
  const requested: string[] = [];
  const client = createApiClient({
    baseUrl: "http://api.example.test",
    fetch: async (url, init) => {
      requested.push(`${init?.method ?? "GET"} ${String(url)}`);
      return Response.json({ learner_id: 3, episodes: [] });
    },
  });

  await client.getWritingHistory(3);
  await client.getWritingHistoryEpisode(3, 7);
  await client.getWritingProgress(3);
  await client.getWritingContext(3);

  assert.deepEqual(requested, [
    "GET http://api.example.test/learners/3/writing/history",
    "GET http://api.example.test/learners/3/writing/history/7",
    "GET http://api.example.test/learners/3/writing/progress",
    "GET http://api.example.test/learners/3/writing/context",
  ]);
});

test("the client surfaces the episode_not_found error envelope", async () => {
  const client = createApiClient({
    baseUrl: "http://api.example.test",
    fetch: async () => Response.json(
      { error: { code: "episode_not_found", message: "Learning episode was not found.", fields: [] } },
      { status: 404 },
    ),
  });

  await assert.rejects(
    () => client.getWritingHistoryEpisode(3, 999),
    (error: unknown) =>
      error instanceof ApiRequestError && error.code === "episode_not_found",
  );
});


test("the client sends the published Agent turn request", async () => {
  let requestedUrl = "";
  let requestedInit: RequestInit | undefined;
  const client = createApiClient({
    baseUrl: "http://api.example.test",
    fetch: async (url, init) => {
      requestedUrl = String(url);
      requestedInit = init;
      return Response.json({});
    },
  });

  await client.agentTurn(3, { turn_type: "continue" });

  assert.equal(requestedUrl, "http://api.example.test/learners/3/agent/turn");
  assert.equal(requestedInit?.method, "POST");
  assert.equal(requestedInit?.body, JSON.stringify({ turn_type: "continue" }));
});