import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API_BASE_URL = "http://localhost:8000";
const PRESENTATION_CACHE_KEY = "ielts-learning-agent.phase5.presentation";

type PlannerVersion =
  | "writing-practice-gap-v1"
  | "writing-practice-gap-memory-v2";

type Phase7Seed = {
  learner_id: number;
  recommendation_id: number;
  planner_version: PlannerVersion;
};

async function seedPlanner(
  request: APIRequestContext,
  plannerVersion: PlannerVersion,
): Promise<Phase7Seed> {
  const response = await request.post(
    `${API_BASE_URL}/e2e/phase7/${plannerVersion}`,
  );
  expect(response.ok()).toBeTruthy();
  return response.json() as Promise<Phase7Seed>;
}

async function openDashboardForLearner(page: Page, learnerId: number): Promise<void> {
  await page.addInitScript(
    ({ cacheKey, id }) => {
      window.localStorage.setItem(
        cacheKey,
        JSON.stringify({
          currentLearnerId: id,
          writingTargetBand: "7.0",
          currentRecommendationId: null,
          currentRecommendation: null,
        }),
      );
    },
    { cacheKey: PRESENTATION_CACHE_KEY, id: learnerId },
  );
  await page.goto("/dashboard");
}

test("Phase 7 v1 recommendation remains actionable without v2 explanation copy", async ({
  page,
  request,
}) => {
  const seeded = await seedPlanner(request, "writing-practice-gap-v1");
  await openDashboardForLearner(page, seeded.learner_id);

  await expect(page.getByRole("button", { name: "生成针对性练习" })).toBeVisible();
  await expect(page.getByText(/^推荐依据：/)).toHaveCount(0);
  await page.getByRole("button", { name: "生成针对性练习" }).click();
  await expect(page).toHaveURL(/\/practice\/\d+$/);
  await expect(page.getByText("训练重点：任务回应（Task Response）")).toBeVisible();
});

test("Phase 7 exact-tie v2 recommendation renders safe Chinese explanation", async ({
  page,
  request,
}) => {
  const seeded = await seedPlanner(
    request,
    "writing-practice-gap-memory-v2",
  );
  await openDashboardForLearner(page, seeded.learner_id);

  const explanation =
    "推荐依据：当前多个能力与目标分差距相同。同等薄弱项仍无法区分，系统按固定优先级选择了这一项。";
  await expect(page.getByText(explanation)).toBeVisible();
  await expect(page.getByText(/planner_context_snapshot|selection_trace/)).toHaveCount(0);

  await page.getByRole("link", { name: "查看写作历史" }).click();
  await expect(page.getByRole("heading", { name: "写作历史" })).toBeVisible();
  await page.locator(".episode-card a").first().click();
  await expect(page.getByRole("heading", { name: "学习记录详情" })).toBeVisible();
  await expect(page.getByText(explanation)).toBeVisible();
});
