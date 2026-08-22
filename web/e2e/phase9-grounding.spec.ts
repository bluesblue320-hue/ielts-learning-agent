import { expect, test } from "@playwright/test";

test("grounded IELTS guidance survives a durable dashboard resume", async ({ page }) => {
  await page.goto("/setup");
  await page.getByRole("button", { name: "开始首次写作" }).click();
  await page.getByLabel("英文 Task 2 题目").fill(
    "Some people think governments should spend more on public transport. Discuss both views and give your opinion.",
  );
  await page.getByLabel("你的英文作文").fill(
    "This response states a clear position, develops relevant supporting ideas, uses examples, and answers both parts of the Writing Task 2 question.",
  );
  await page.getByRole("button", { name: "提交并获取评估" }).click();
  await page.getByRole("button", { name: "应用学习更新" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  const guidance = page.getByRole("region", { name: "本次写作指导" });
  await expect(guidance).toBeVisible();
  await expect(guidance.getByText(/当前水平：6\.00 · 目标：7\.0/)).toBeVisible();
  await expect(guidance.getByText("主要差距与下一步：", { exact: false })).toBeVisible();
  await expect(guidance.getByText("IELTS 对该维度的要求：", { exact: false })).toBeVisible();
  const descriptorSources = guidance.getByRole("link", {
    name: /IELTS Writing Band Descriptors/,
  });
  await expect(descriptorSources).toHaveCount(2);
  await expect(descriptorSources.first()).toHaveAttribute("href", /^https:\/\/ielts\.org\//);
  await expect(guidance).not.toContainText("writing-task-response-band-");
  await expect(guidance).not.toContainText("ielts-writing-band-descriptors-2023");

  const persistedGuidance = await guidance.textContent();
  await page.reload();
  const resumedGuidance = page.getByRole("region", { name: "本次写作指导" });
  await expect(resumedGuidance).toBeVisible();
  await expect.poll(() => resumedGuidance.textContent()).toBe(persistedGuidance);
});
