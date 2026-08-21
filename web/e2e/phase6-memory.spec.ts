import { expect, test, type Page } from "@playwright/test";

async function openCurrentPractice(page: Page): Promise<void> {
  const resumePractice = page.getByRole("link", { name: "继续完成练习" });
  const generatePractice = page.getByRole("button", { name: "生成针对性练习" });
  await expect.poll(async () => (
    await resumePractice.count() + await generatePractice.count()
  )).toBeGreaterThan(0);
  if (await resumePractice.count() > 0) {
    await resumePractice.click();
  } else {
    await generatePractice.click();
  }
  await expect(page).toHaveURL(/\/practice\/\d+$/);
}

test("learner sees longitudinal history, progress, and server-authoritative resume", async ({ page }) => {
  // 1. Create learner + initial writing (evaluation 1).
  await page.goto("/setup");
  await page.getByRole("button", { name: "开始首次写作" }).click();
  await page.getByLabel("英文 Task 2 题目").fill("Some people think governments should spend more on public transport. Discuss both views and give your opinion.");
  await page.getByLabel("你的英文作文").fill("This is a sufficiently detailed IELTS Task 2 response with a clear position, developed supporting ideas, examples, and a conclusion that addresses the question in full.");
  await page.getByRole("button", { name: "提交并获取评估" }).click();
  await expect(page.getByRole("heading", { name: /综合分数/ })).toBeVisible();
  await page.getByRole("button", { name: "应用学习更新" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText("已采纳证据：1").first()).toBeVisible();

  // 2. First targeted practice cycle (evaluation 2).
  await openCurrentPractice(page);
  const firstPracticeUrl = page.url();
  await page.getByLabel("你的英文作文").fill("First targeted practice essay with specific supporting examples and coherent paragraphs throughout.");
  await page.getByRole("button", { name: "提交作文并由学习助手继续" }).click();
  await expect.poll(() => page.url()).not.toBe(firstPracticeUrl);
  await page.goto("/dashboard");
  await expect(page.getByText("已采纳证据：2").first()).toBeVisible();

  // 3. Second targeted practice cycle (evaluation 3) -> three observations.
  await openCurrentPractice(page);
  const secondPracticeUrl = page.url();
  await page.getByLabel("你的英文作文").fill("Second targeted practice essay with precise examples and accurate grammar throughout the response.");
  await page.getByRole("button", { name: "提交作文并由学习助手继续" }).click();
  await expect.poll(() => page.url()).not.toBe(secondPracticeUrl);
  await page.goto("/dashboard");
  await expect(page.getByText("已采纳证据：3").first()).toBeVisible();

  // 4. History: deterministic ordering and episode types (latest first).
  await page.getByRole("link", { name: "历史", exact: true }).click();
  await expect(page.getByRole("heading", { name: "写作历史" })).toBeVisible();
  const episodeCards = page.locator(".episode-card");
  await expect(episodeCards).toHaveCount(3);
  await expect(episodeCards.nth(0)).toContainText("针对性练习");
  await expect(episodeCards.nth(1)).toContainText("针对性练习");
  await expect(episodeCards.nth(2)).toContainText("首次写作");

  // 5. Episode detail: progressive disclosure down to raw L0 content.
  await episodeCards.nth(0).locator("a").click();
  await expect(page.getByRole("heading", { name: "学习记录详情" })).toBeVisible();
  await expect(page.getByText("写作题目")).toBeVisible();
  await expect(page.getByText("你的作文")).toBeVisible();
  await expect(page.getByText("记录来源信息")).toBeVisible();

  // 6. Progress: backend-derived trend and persistent-gap presentation.
  await page.getByRole("link", { name: "进度", exact: true }).click();
  await expect(page.getByRole("heading", { name: "学习进度" })).toBeVisible();
  await expect(page.getByText("稳定").first()).toBeVisible();
  await expect(page.getByText("持续低于目标：是").first()).toBeVisible();

  // 7. Dashboard resume: server-authoritative context (new practice decision).
  await page.getByRole("link", { name: "学习概览", exact: true }).click();
  await expect(page.getByText("继续学习")).toBeVisible();
  const resumePractice = page.getByRole("link", { name: "继续完成练习" });
  const generatePractice = page.getByRole("button", { name: "生成针对性练习" });
  await expect.poll(async () => (
    await resumePractice.count() + await generatePractice.count()
  )).toBeGreaterThan(0);
});
