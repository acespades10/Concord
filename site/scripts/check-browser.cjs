const { chromium } = require("../../apps/web/node_modules/@playwright/test");
const {
  readFileSync,
  mkdirSync,
  writeFileSync,
  existsSync,
} = require("node:fs");
const { resolve, extname } = require("node:path");
const http = require("node:http");
const assert = require("node:assert/strict");
const root = resolve(__dirname, "..");
const out = resolve(__dirname, "../../.local/site-qa");
const types = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "text/javascript",
  ".woff2": "font/woff2",
  ".webp": "image/webp",
  ".json": "application/json",
  ".jsonl": "application/x-ndjson",
  ".md": "text/plain",
};
mkdirSync(out, { recursive: true });
const server = http.createServer((req, res) => {
  const file = resolve(
    root,
    "." +
      decodeURI(
        req.url.split("?")[0] === "/" ? "/index.html" : req.url.split("?")[0],
      ),
  );
  if (!file.startsWith(root) || !existsSync(file)) {
    res.writeHead(404);
    return res.end("Not found");
  }
  res.setHeader(
    "Content-Type",
    types[extname(file)] || "application/octet-stream",
  );
  res.end(readFileSync(file));
});
(async () => {
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const url = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROME_PATH || undefined,
  });
  const report = { viewports: [], errors: [] };
  try {
    for (const [width, height] of [
      [1440, 900],
      [1024, 768],
      [820, 1180],
      [768, 1024],
      [390, 844],
      [320, 800],
    ]) {
      const page = await browser.newPage({
        viewport: { width, height },
        reducedMotion: "reduce",
      });
      page.on("pageerror", (e) => report.errors.push(String(e)));
      page.on("response", (r) => {
        if (r.status() >= 400) report.errors.push(`${r.status()} ${r.url()}`);
      });
      await page.goto(url);
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(350);
      const initial = await page.evaluate(() => ({
        width: innerWidth,
        scroll: document.documentElement.scrollWidth,
        hero: document.querySelector(".hero").getBoundingClientRect().height,
        sections: [
          ...document.querySelectorAll("main>section,footer.closing"),
        ].map((s) => ({
          id: s.id,
          height: s.getBoundingClientRect().height,
          overflow: s.scrollHeight > s.clientHeight + 2,
        })),
        images: [...document.images].map((i) => ({
          src: i.getAttribute("src"),
          loaded: i.complete && i.naturalWidth > 0,
        })),
      }));
      assert(
        initial.sections.every((s) => !s.overflow),
        JSON.stringify(initial.sections),
      );
      assert(
        initial.scroll <= width,
        `Horizontal overflow at ${width}: ${initial.scroll}`,
      );
      await page.locator("#tab-review").click();
      await page.waitForTimeout(50);
      assert(await page.locator("#panel-review").isVisible());
      await page.locator("#tab-review").press("ArrowRight");
      assert(await page.locator("#panel-export").isVisible());
      await page.locator("#tab-votes").click();
      assert(await page.locator("#panel-votes").isVisible());
      if (width < 1024) {
        await page.locator(".nav__toggle").click();
        assert.equal(
          await page.locator(".nav__toggle").getAttribute("aria-expanded"),
          "true",
        );
        assert(await page.locator("main").evaluate((e) => e.inert));
        await page.keyboard.press("Escape");
        assert.equal(
          await page.locator(".nav__toggle").getAttribute("aria-expanded"),
          "false",
        );
        await page.locator(".nav__toggle").click();
        await page.locator('.nav__links a[href="#workflow"]').click();
        assert.equal(
          await page.locator(".nav__toggle").getAttribute("aria-expanded"),
          "false",
        );
      }
      await page
        .context()
        .grantPermissions(["clipboard-read", "clipboard-write"]);
      await page.locator("[data-copy]").click();
      await page.waitForFunction(() =>
        document.querySelector(".copy-status").textContent.includes("copied"),
      );
      assert.match(await page.locator(".copy-status").innerText(), /copied/);
      const copied = await page.evaluate(() => navigator.clipboard.readText());
      assert(copied.includes("benchmarks/run.py"));
      await page.locator(".product-screen").scrollIntoViewIfNeeded();
      await page.evaluate(() =>
        Promise.all([...document.images].map((i) => i.decode())),
      );
      await page.waitForTimeout(150);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForTimeout(150);
      await page.screenshot({
        path: resolve(out, `verified-${width}.png`),
        fullPage: true,
      });
      report.viewports.push({
        ...initial,
        controls: "tabs, arrow keys, copy, menu and Escape passed",
      });
      await page.close();
    }
    const auditContext = await browser.newContext({
      viewport: { width: 1440, height: 900 },
    });
    const page = await auditContext.newPage();
    await page.goto(url);
    const AxeBuilder =
      require("../../apps/web/node_modules/@axe-core/playwright").default;
    const axeResult = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    report.accessibility = {
      passes: axeResult.passes.length,
      violations: axeResult.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        nodes: v.nodes.map((n) => ({
          html: n.html,
          summary: n.failureSummary,
        })),
      })),
    };
    assert.equal(report.errors.length, 0, JSON.stringify(report.errors));
    assert.equal(
      report.accessibility.violations.length,
      0,
      JSON.stringify(report.accessibility.violations),
    );
    report.passed = true;
  } catch (e) {
    report.passed = false;
    report.failure = String(e);
    throw e;
  } finally {
    writeFileSync(
      resolve(out, "functional-report.json"),
      JSON.stringify(report, null, 2),
    );
    await browser.close();
    server.close();
  }
  console.log(JSON.stringify(report, null, 2));
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
  server.close();
});
