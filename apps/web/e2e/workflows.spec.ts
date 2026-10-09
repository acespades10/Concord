import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function login(page: Page, account: string) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(`${account}@concord.demo`);
  await page.getByLabel("Password", { exact: true }).fill("concord-demo-2026");
  const signedIn = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/auth/login") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Enter workspace" }).click();
  const response = await signedIn;
  expect(response.status()).toBe(200);
  expect((await response.json()).user.email).toBe(`${account}@concord.demo`);
  await expect(
    page.getByRole("heading", { name: "Your workspace." }),
  ).toBeVisible({ timeout: 60000 });
}

test("workspace is accessible and responsive", async ({ page }) => {
  await login(page, "admin");
  await page.screenshot({
    path: "../../artifacts/workspace-desktop.png",
    fullPage: true,
  });
  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        summary: n.failureSummary,
      })),
    })),
  ).toEqual([]);
  await page.screenshot({
    path: "../../artifacts/workspace-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("button", { name: "Open navigation" }),
  ).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBeTruthy();
  await page.screenshot({
    path: "../../artifacts/workspace-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(
    page.getByRole("link", { name: "Quality overview", exact: true }),
  ).toBeVisible();
});

for (const mode of ["rating", "ner", "ab"] as const) {
  test(`${mode}: admin imports, three raters submit, reviewer adjudicates and exports`, async ({
    browser,
  }) => {
    const adminContext = await browser.newContext();
    const admin = await adminContext.newPage();
    await login(admin, "admin");
    const name = `E2E ${mode} ${Date.now()}`;
    await admin.getByRole("button", { name: "New project" }).click();
    await admin.getByLabel("Project name").fill(name);
    await admin.getByLabel("Annotation mode").selectOption(mode);
    if (mode !== "ab")
      await admin
        .getByLabel(mode === "rating" ? /Rating labels/ : /Entity types/)
        .fill(mode === "rating" ? "Bad, Good" : "PERSON, LOCATION");
    await admin
      .getByRole("button", { name: "Create project", exact: true })
      .click();
    await admin
      .getByRole("link")
      .filter({ has: admin.getByRole("heading", { name, exact: true }) })
      .click();
    await expect(admin).toHaveURL(/\/projects\/[0-9a-f-]+$/);
    const projectUrl = admin.url();
    await admin.getByRole("tab", { name: "Project setup" }).click();
    for (const person of ["Sam Rivera", "Taylor Chen", "Casey Park"])
      await admin.getByLabel(new RegExp(person)).check();
    await admin.getByRole("button", { name: "Save team" }).click();
    await expect(admin.getByRole("status")).toContainText("Team updated");
    const item =
      mode === "rating"
        ? {
            external_id: "test-001",
            prompt: "Welcome the team",
            response: "Hello 🌏!\nWelcome aboard.",
          }
        : mode === "ner"
          ? { external_id: "test-001", text: "Maya in Taipei 🌿" }
          : {
              external_id: "test-001",
              prompt: "Welcome the team",
              response_a: "Hello A",
              response_b: "Hello B",
            };
    await admin.getByLabel("Dataset file").setInputFiles({
      name: "test.jsonl",
      mimeType: "application/x-ndjson",
      buffer: Buffer.from(JSON.stringify(item)),
    });
    await admin.getByRole("button", { name: "Validate & import" }).click();
    await expect(admin.getByRole("status")).toContainText("1 items imported");
    await admin.getByRole("button", { name: "Activate project" }).click();
    await expect(admin.getByRole("status")).toContainText(
      "Project state updated",
    );
    const reviewerContext = await browser.newContext();
    const reviewer = await reviewerContext.newPage();
    await login(reviewer, "reviewer");
    await reviewer.goto(projectUrl);
    await expect(reviewer.getByText("Live updates connected")).toBeVisible();
    for (let i = 1; i <= 3; i++) {
      const context = await browser.newContext();
      const rater = await context.newPage();
      await login(rater, `annotator${i}`);
      await rater.goto(projectUrl);
      await rater.getByRole("button", { name: "Start annotating" }).click();
      if (mode === "rating")
        await rater
          .getByRole("radio", { name: i === 3 ? /Bad/ : /Good/ })
          .check();
      if (mode === "ab")
        await rater
          .getByRole("radio", {
            name: i === 3 ? "Prefer A" : "Equally good / Tie",
          })
          .check();
      if (mode === "ner" && i < 3) {
        const token = rater.getByRole("button", { name: "Maya, token 1" });
        await token.click();
        await token.click();
      }
      if (mode === "rating" && i === 1) {
        await expect(rater.getByRole("status")).toHaveText("All changes saved");
        await rater
          .getByRole("link", { name: "All projects", exact: true })
          .click();
        await rater
          .getByRole("link")
          .filter({ has: rater.getByRole("heading", { name, exact: true }) })
          .click();
        await expect(rater.getByRole("radio", { name: /Good/ })).toBeChecked();
      }
      await rater.getByRole("button", { name: "Submit & continue" }).click();
      await expect(
        rater.getByRole("heading", { name: "You’re all caught up." }),
      ).toBeVisible();
      await expect(
        rater.getByRole("tab", { name: "Quality & agreement" }),
      ).toHaveCount(0);
      await context.close();
    }
    await expect(reviewer.getByText("3 of 3 annotations")).toBeVisible();
    await reviewer.getByRole("tab", { name: "Review queue" }).click();
    await reviewer.getByRole("button", { name: /test-001/ }).click();
    await reviewer
      .getByLabel("Rationale", { exact: true })
      .fill(
        "Reviewed all three independent judgments against the project guidelines.",
      );
    await reviewer.getByRole("button", { name: "Save final decision" }).click();
    await expect(
      reviewer.getByRole("heading", { name: "You’re on the same page." }),
    ).toBeVisible();
    await reviewer.getByRole("tab", { name: "Export dataset" }).click();
    for (const format of ["JSONL", "Parquet", "Hugging Face"]) {
      await reviewer.getByRole("radio", { name: new RegExp(format) }).check();
      const downloadPromise = reviewer.waitForEvent("download");
      await reviewer.getByRole("button", { name: "Download dataset" }).click();
      const download = await downloadPromise;
      expect(download.suggestedFilename()).toMatch(/\.zip$/);
      expect(await download.failure()).toBeNull();
    }
    await reviewerContext.close();
    await adminContext.close();
  });
}
