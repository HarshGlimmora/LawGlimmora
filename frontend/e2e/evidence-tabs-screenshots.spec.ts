import { test, type Page } from "@playwright/test";

/** One-off: capture a full-page screenshot of every Evidence Vault tab.
 *  Run with `npx playwright test e2e/evidence-tabs-screenshots.spec.ts`.
 *  Artifacts land in `playwright-screenshots/<tab>.png`. */

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in as Anika" }).click();
  await page.waitForURL("**/dashboard", { timeout: 10_000 });
}

const TABS = [
  ["upload", /upload & ingest/i],
  ["canonical-store", /canonical store/i],
  ["entities", /entities/i],
  ["contradictions", /contradictions/i],
  ["missing", /missing evidence/i],
  ["chat", /evidence chat/i],
  ["analysis", /final analysis/i],
] as const;

test("screenshot every evidence-vault tab", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/cases/1/evidence");
  await page.waitForLoadState("networkidle");

  for (const [slug, label] of TABS) {
    await page.getByRole("tab", { name: label }).click();
    await page.waitForLoadState("networkidle");
    // Small settle for any post-fetch render
    await page.waitForTimeout(400);
    await page.screenshot({
      path: `playwright-screenshots/${slug}.png`,
      fullPage: true,
    });
  }
});
