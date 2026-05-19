import { expect, test, type Page } from "@playwright/test";

/**
 * Research & Precedent Engine — UI smoke for every tab.
 *
 * Prereqs:
 *   - uvicorn on :8000 with seeded users (Anika has case 1)
 *   - At least one precedent ingested into case 1 (any text via /ingest-text)
 *   - At least one research session saved
 *   - The downstream payload built once
 */

const PATH = "/cases/1/research";

async function signInAsAnika(page: Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in as Anika" }).click();
  await page.waitForURL("**/dashboard", { timeout: 10_000 });
}

test.beforeEach(async ({ context }) => {
  await context.clearCookies();
});

test("research page renders the 6 tabs", async ({ page }) => {
  await signInAsAnika(page);
  await page.goto(PATH);
  await page.waitForLoadState("networkidle");

  for (const name of [
    /^Ask$/,
    /^Corpus$/,
    /^Authorities$/,
    /^Timeline$/,
    /^Sessions$/,
    /^Connections$/,
  ]) {
    await expect(page.getByRole("tab", { name })).toBeVisible();
  }
  // No "coming in this milestone" placeholders anywhere on the page.
  await expect(page.getByText(/coming in this milestone/i)).toHaveCount(0);
});

test("Ask tab renders query box + filters", async ({ page }) => {
  await signInAsAnika(page);
  await page.goto(PATH);
  await page.waitForLoadState("networkidle");
  // Use input ids so we side-step text collisions with the page header,
  // and look for the query <textarea> + all 6 filter inputs + the submit
  // button. Each lives only inside the Ask tab.
  await expect(page.locator("textarea").first()).toBeVisible();
  await expect(page.locator("#jurisdiction")).toBeVisible();
  await expect(page.locator("#courts")).toBeVisible();
  await expect(page.locator("#issues")).toBeVisible();
  await expect(page.locator("#practice")).toBeVisible();
  await expect(page.locator("#date-from")).toBeVisible();
  await expect(page.locator("#date-to")).toBeVisible();
  await expect(page.locator("#topk")).toBeVisible();
  await expect(page.getByRole("button", { name: /run research/i })).toBeVisible();
});

test("Corpus tab renders ingest panel + a corpus list with the seeded doc",
  async ({ page }) => {
    await signInAsAnika(page);
    await page.goto(PATH);
    await page.getByRole("tab", { name: /^Corpus$/ }).click();
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("button", { name: /ingest precedent/i }))
      .toBeVisible();
    // The seeded "Acme Industries Pvt Ltd vs Zenith Holdings Pvt Ltd" must show.
    await expect(page.getByText(/Acme Industries Pvt Ltd vs Zenith/i).first())
      .toBeVisible();
  });

test("Authorities tab renders citation lookup + browse table", async ({
  page,
}) => {
  await signInAsAnika(page);
  await page.goto(PATH);
  await page.getByRole("tab", { name: /^Authorities$/ }).click();
  await page.waitForLoadState("networkidle");
  await expect(page.getByText(/^Citation lookup$/i)).toBeVisible();
  await expect(page.getByText(/^Find similar precedents$/i)).toBeVisible();
  // Browse table header
  await expect(page.getByText(/^Title$/, { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/^Binding$/, { exact: true }).first()).toBeVisible();
});

test("Timeline tab renders dated events or a build-now CTA", async ({
  page,
}) => {
  await signInAsAnika(page);
  await page.goto(PATH);
  await page.getByRole("tab", { name: /^Timeline$/ }).click();
  await page.waitForLoadState("networkidle");
  const timeline = page.getByText(/^Timeline · \d+ events?$/);
  const cta = page.getByText(/timeline not built yet/i);
  await expect(timeline.or(cta)).toBeVisible({ timeout: 15_000 });
});

test("Sessions tab renders the saved memo + export buttons", async ({
  page,
}) => {
  await signInAsAnika(page);
  await page.goto(PATH);
  await page.getByRole("tab", { name: /^Sessions$/ }).click();
  await page.waitForLoadState("networkidle");
  // The page subtitle contains the phrase "research memory" — use the exact
  // Eyebrow "Research memo" to disambiguate.
  await expect(page.getByText("Research memo", { exact: true })).toBeVisible();
  // Export buttons for JSON / MD / PDF
  await expect(page.getByRole("button", { name: /^JSON$/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^MD$/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^PDF$/ })).toBeVisible();
  // Feedback buttons
  await expect(page.getByRole("button", { name: /^Good$/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Bad$/ })).toBeVisible();
});

test("Connections tab renders signals + top authorities or a build CTA",
  async ({ page }) => {
    await signInAsAnika(page);
    await page.goto(PATH);
    await page.getByRole("tab", { name: /^Connections$/ }).click();
    await page.waitForLoadState("networkidle");
    const built = page.getByText(/^Case-strength signals$/i);
    const cta = page.getByText(/downstream payload not built yet/i);
    await expect(built.or(cta)).toBeVisible({ timeout: 15_000 });
  });
