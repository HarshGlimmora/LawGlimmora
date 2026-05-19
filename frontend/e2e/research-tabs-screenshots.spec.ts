import { test, type Page } from "@playwright/test";

/** Full-page screenshots of every Research Engine tab. */

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in as Anika" }).click();
  await page.waitForURL("**/dashboard", { timeout: 10_000 });
}

const TABS = [
  ["ask", /^Ask$/],
  ["corpus", /^Corpus$/],
  ["authorities", /^Authorities$/],
  ["timeline", /^Timeline$/],
  ["sessions", /^Sessions$/],
  ["connections", /^Connections$/],
] as const;

test("screenshot every research tab", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/cases/1/research");
  await page.waitForLoadState("networkidle");

  for (const [slug, label] of TABS) {
    await page.getByRole("tab", { name: label }).click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(400);
    await page.screenshot({
      path: `playwright-screenshots/research-${slug}.png`,
      fullPage: true,
    });
  }
});
