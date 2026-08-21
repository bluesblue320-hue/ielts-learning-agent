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
  const firstPracticeUrl = page.url();
  const firstPracticeId = firstPracticeUrl.match(/\/practice\/(\d+)$/)?.[1];
  expect(firstPracticeId).toBeTruthy();

  await page.getByLabel("你的英文作文").fill(
    "This targeted practice response develops a clear position, explains each supporting point, uses specific examples, and concludes directly against the authoritative question.",
  );
  await page.getByRole("button", { name: "提交作文并由学习助手继续" }).click();
  await expect.poll(() => page.url()).not.toBe(firstPracticeUrl);

  const terminalState = page.getByText("系统暂时没有建议的下一步练习。");
  if (/\/dashboard$/.test(page.url())) {
    const resumeNextPractice = page.getByRole("link", { name: "继续完成练习" });
    await expect(page.getByText("已采纳证据：2").first()).toBeVisible();
    await expect.poll(async () => (
      await resumeNextPractice.count() + await terminalState.count()
    )).toBeGreaterThan(0);

    if (await resumeNextPractice.count() > 0) {
      const resumeHref = await resumeNextPractice.getAttribute("href");
      expect(resumeHref).toMatch(/^\/practice\/\d+$/);
      expect(resumeHref).not.toBe(`/practice/${firstPracticeId}`);
      await resumeNextPractice.click();
      await expect(page).toHaveURL(new RegExp(`${resumeHref}$`));
    }
  }

  if (/\/practice\/\d+$/.test(page.url())) {
    const nextPracticeUrl = page.url();
    const nextPracticeId = nextPracticeUrl.match(/\/practice\/(\d+)$/)?.[1];
    expect(nextPracticeUrl).not.toBe(firstPracticeUrl);
    expect(nextPracticeId).toBeTruthy();

    await expect(page.getByRole("heading", { name: "Writing Task 2" })).toBeVisible();
    await expect(page.getByText("训练重点：", { exact: false })).toBeVisible();
    await expect(page.getByLabel("你的英文作文")).toBeVisible();
    const persistedQuestion = await page.locator(".question-copy").innerText();
    const persistedFocus = await page.getByRole("heading", { level: 1 }).innerText();

    await page.reload();
    await expect(page).toHaveURL(nextPracticeUrl);
    await expect(page.getByRole("heading", { name: "Writing Task 2" })).toBeVisible();
    await expect(page.locator(".question-copy")).toHaveText(persistedQuestion);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(persistedFocus);
    await expect(page.getByText("训练重点：", { exact: false })).toBeVisible();
    await expect(page.getByLabel("你的英文作文")).toBeVisible();

    await page.goto("/dashboard");
    await expect(page.locator(`a[href="/practice/${nextPracticeId}"]`)).toBeVisible();
    await expect(page.locator(`a[href="/practice/${firstPracticeId}"]`)).toHaveCount(0);
    await expect(page.getByText("已采纳证据：2").first()).toBeVisible();

    await page.reload();
    await expect(page.locator(`a[href="/practice/${nextPracticeId}"]`)).toBeVisible();
    await expect(page.locator(`a[href="/practice/${firstPracticeId}"]`)).toHaveCount(0);
    await expect(page.getByText("已采纳证据：2").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "完成练习并获取下一步建议" })).toHaveCount(0);
  } else {
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(terminalState).toBeVisible();
    await expect(page.locator(`a[href="/practice/${firstPracticeId}"]`)).toHaveCount(0);
    await expect(page.getByText("已采纳证据：2").first()).toBeVisible();

    await page.reload();
    await expect(terminalState).toBeVisible();
    await expect(page.locator(`a[href="/practice/${firstPracticeId}"]`)).toHaveCount(0);
    await expect(page.getByText("已采纳证据：2").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "完成练习并获取下一步建议" })).toHaveCount(0);
  }
});
