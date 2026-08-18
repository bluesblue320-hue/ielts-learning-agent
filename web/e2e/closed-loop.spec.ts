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
  await expect(page.getByRole("heading", { name: "你的写作学习状态" })).toBeVisible();
  await page.getByRole("button", { name: "生成针对性练习" }).click();
  await expect(page).toHaveURL(/\/practice\/\d+$/);
  await expect(page.getByText("Some people believe governments should spend more on public transport")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Writing Task 2", exact: true })).toBeVisible();
  await page.getByLabel("你的英文作文").fill("This targeted practice essay develops a clear position with relevant examples, coherent paragraphs, and accurate grammar throughout the response.");
  await page.getByRole("button", { name: "提交作文并获取评估" }).click();
  await expect(page.getByText("作文已提交，以下是持久化评估。")).toBeVisible();
  await expect(page.getByRole("heading", { name: /综合分数/ })).toBeVisible();
  await page.getByRole("button", { name: "完成练习并获取下一步建议" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "你的写作学习状态" })).toBeVisible();
  await expect(page.getByRole("button", { name: "生成针对性练习" })).toBeVisible();
});