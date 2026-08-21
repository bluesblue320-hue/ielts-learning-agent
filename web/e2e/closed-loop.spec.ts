import { expect, test } from "@playwright/test";

test("Chinese learner completes one authoritative adaptive writing loop", async ({ page }) => {
  await page.goto("/setup");
  await page.getByRole("button", { name: "开始首次写作" }).click();
  await page.getByLabel("英文 Task 2 题目").fill("Some people think governments should spend more on public transport. Discuss both views and give your opinion.");
  await page.getByLabel("你的英文作文").fill("This is a sufficiently detailed IELTS Task 2 response with a clear position, developed supporting ideas, examples, and a conclusion that addresses the question in full.");
  await page.getByRole("button", { name: "提交并获取评估" }).click();
  await expect(page.getByRole("heading", { name: /综合分数/ })).toBeVisible();
  await page.getByRole("button", { name: "应用学习更新" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText("已采纳证据：1").first()).toBeVisible();
  await expect(page.getByText("任务回应（Task Response）").first()).toBeVisible();
  await expect(page.getByText("训练重点：任务回应（Task Response）")).toBeVisible();

  await page.getByRole("button", { name: "生成针对性练习" }).click();
  await expect(page).toHaveURL(/\/practice\/\d+$/);
  const completedPracticeUrl = page.url();
  const completedPracticeId = completedPracticeUrl.match(/\/practice\/(\d+)$/)?.[1];
  expect(completedPracticeId).toBeTruthy();
  await expect(page.getByText("训练重点：任务回应（Task Response）")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Writing Task 2", exact: true })).toBeVisible();
  await page.getByLabel("你的英文作文").fill("This targeted practice essay develops a clear position with relevant examples, coherent paragraphs, and accurate grammar throughout the response.");
  await page.getByRole("button", { name: "提交作文并由学习助手继续" }).click();
  await expect.poll(() => page.url()).not.toBe(completedPracticeUrl);

  await page.goto("/dashboard");
  await expect(page.getByText("已采纳证据：2").first()).toBeVisible();
  await expect(page.locator(`a[href="/practice/${completedPracticeId}"]`)).toHaveCount(0);
  const resumePractice = page.getByRole("link", { name: "继续完成练习" });
  const generatePractice = page.getByRole("button", { name: "生成针对性练习" });
  await expect.poll(async () => (
    await resumePractice.count() + await generatePractice.count()
  )).toBeGreaterThan(0);
});
