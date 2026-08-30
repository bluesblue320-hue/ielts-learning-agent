import { expect, test } from "@playwright/test";

test("learner browses the canonical Wiki hierarchy and descriptor provenance", async ({ page }) => {
  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "Writing Task 2 知识导航" })).toBeVisible();

  const directory = page.getByRole("navigation", { name: "Writing Task 2 知识目录" });
  await directory.getByRole("link", { name: /Assessment Criteria/ }).click();
  await expect(page).toHaveURL(/\/knowledge\/writing-task2-assessment$/);

  await page.getByRole("link", { name: "Task Response", exact: true }).click();
  await expect(page).toHaveURL(/\/knowledge\/writing-task2-task-response$/);
  await page.getByRole("link", { name: "Task Response Band 7", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Task Response Band 7" })).toBeVisible();
  await expect(page.getByText("Main task parts covered; clear position; support may lack focus.")).toBeVisible();
  await expect(page.getByRole("link", { name: /IELTS Writing Band Descriptors/ })).toHaveAttribute(
    "href",
    /^https:\/\/ielts\.org\//,
  );
  await expect(page.getByText(/Writing Task 2 \/ Task Response \/ Band 7/)).toBeVisible();

  await page.getByRole("link", { name: /查看上一档评分描述：Task Response Band 6/ }).click();
  await expect(page).toHaveURL(/band-6$/);
  await page.getByRole("link", { name: /查看下一档评分描述：Task Response Band 7/ }).click();
  await expect(page).toHaveURL(/band-7$/);

  const breadcrumbs = page.getByRole("navigation", { name: "知识页路径" });
  await breadcrumbs.getByRole("link", { name: "Writing Task 2" }).click();
  await page.getByRole("link", { name: "Task Rules", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Task Rules" })).toBeVisible();
  await page.getByRole("navigation", { name: "知识页路径" })
    .getByRole("link", { name: "Writing Task 2", exact: true })
    .click();
  await page.getByRole("link", { name: "Task Types", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Task Types" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Opinion", exact: true })).toBeVisible();
});

test("grounded guidance navigates through canonical knowledge IDs to Wiki pages", async ({ page }) => {
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
  const wikiLink = guidance.getByRole("link", { name: /查看知识页：Task Response Band 6/ });
  await expect(wikiLink).toBeVisible();
  await wikiLink.click();
  await expect(page).toHaveURL(/\/knowledge\/writing-task2-task-response-band-6$/);
  await expect(page.getByRole("heading", { name: "Task Response Band 6" })).toBeVisible();
});
