import { expect, test } from "@playwright/test";

test("Agent continue generates once and stops at the human essay boundary", async ({ page }) => {
  await page.goto("/setup");
  await page.getByRole("button", { name: "开始首次写作" }).click();
  await page.getByLabel("英文 Task 2 题目").fill(
    "Some people think governments should spend more on public transport. Discuss both views and give your opinion.",
  );
  await page.getByLabel("你的英文作文").fill(
    "This is a sufficiently detailed IELTS Task 2 response with a clear position, developed supporting ideas, examples, and a conclusion that addresses the question in full.",
  );
  await page.getByRole("button", { name: "提交并获取评估" }).click();
  await page.getByRole("button", { name: "应用学习更新" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByRole("button", { name: "使用学习助手继续" }).click();
  await expect(page.getByText("学习助手状态：下一份针对性练习已准备好。")).toBeVisible();
  await expect(page.getByText("生成针对性练习：已生成练习", { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByRole("link", { name: "开始本次练习" }).click();
  await expect(page).toHaveURL(/\/practice\/\d+$/);
});