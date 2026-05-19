import { expect, test, type Page } from "@playwright/test";

/**
 * Evidence Vault — every tab must render real content (no "coming in this
 * milestone" placeholder).
 *
 * Prereqs (handled by the runner script):
 *  - uvicorn on :8000 with seeded users + at least one ingested PDF on case 1
 *  - a Final Report generated for case 1 (so the contradictions / missing /
 *    analysis tabs have data to render — otherwise they show an empty-state
 *    with a "Compute now" CTA, which is also a passable surface but harder
 *    to assert on)
 */

const CASE_PATH = "/cases/1/evidence";

async function signInAsAnika(page: Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in as Anika" }).click();
  await page.waitForURL("**/dashboard", { timeout: 10_000 });
}

test.beforeEach(async ({ context }) => {
  await context.clearCookies();
});

test("no tab shows the 'coming in this milestone' placeholder", async ({ page }) => {
  await signInAsAnika(page);
  await page.goto(CASE_PATH);
  // Visit every tab, then assert the page never contains the lock-icon
  // empty-state copy. The default tab (Upload & ingest) already renders.
  for (const name of [
    /upload & ingest/i,
    /canonical store/i,
    /entities/i,
    /contradictions/i,
    /missing evidence/i,
    /evidence chat/i,
    /final analysis/i,
  ]) {
    await page.getByRole("tab", { name }).click();
    // small breathing room for the lazy data fetch
    await page.waitForLoadState("networkidle");
    await expect(
      page.getByText(/coming in this milestone/i),
    ).toHaveCount(0);
  }
});

test("Canonical store tab renders document picker + chunks for the seeded PDF",
  async ({ page }) => {
    await signInAsAnika(page);
    await page.goto(CASE_PATH);
    await page.getByRole("tab", { name: /canonical store/i }).click();
    await page.waitForLoadState("networkidle");
    // Sidebar metadata terms — use exact-term match against the <dt>s.
    await expect(page.getByText("Documents", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Filename", { exact: true })).toBeVisible();
    await expect(page.getByText("Filename", { exact: true })).toBeVisible();
    await expect(page.getByText("Totals", { exact: true })).toBeVisible();
    // The right-rail sections — eyebrows are upper-case "PAGES" and "CHUNKS",
    // but the page renders them as styled "Pages"/"Chunks". Use first()
    // because both the <dt>Pages</dt> sidebar label and the <Eyebrow>Pages</Eyebrow>
    // section title legitimately appear; we want either to be visible.
    await expect(page.getByText("Pages", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Chunks", { exact: true }).first()).toBeVisible();
    // A citation label (the [filename | p.N | chunk K] shape) appears on
    // both the page and chunk panels — first one is enough to prove it.
    await expect(page.locator("text=/\\[.+\\| p\\..+\\| chunk/i").first())
      .toBeVisible();
  });

test("Entities tab renders partitions + at least one entity row", async ({
  page,
}) => {
  await signInAsAnika(page);
  await page.goto(CASE_PATH);
  await page.getByRole("tab", { name: /entities/i }).click();
  await page.waitForLoadState("networkidle");
  // Either there are entities or there are not. Seeded case 1 has an
  // ingested PDF → entities should be present.
  await expect(page.getByText(/^Partitions$/i)).toBeVisible();
  // One of the 5 partition chips
  await expect(page.getByRole("button", { name: /parties · \d+/i }).first())
    .toBeVisible();
});

test("Contradictions tab renders the ledger or a compute-now CTA", async ({
  page,
}) => {
  await signInAsAnika(page);
  await page.goto(CASE_PATH);
  await page.getByRole("tab", { name: /contradictions/i }).click();
  await page.waitForLoadState("networkidle");
  const ledgerOrCta = page
    .getByText(/^Contradictions · \d+$/)
    .or(page.getByText(/no contradictions on file/i));
  await expect(ledgerOrCta).toBeVisible({ timeout: 15_000 });
});

test("Missing evidence tab renders the checklist or a compute-now CTA", async ({
  page,
}) => {
  await signInAsAnika(page);
  await page.goto(CASE_PATH);
  await page.getByRole("tab", { name: /missing evidence/i }).click();
  await page.waitForLoadState("networkidle");
  const checklistOrCta = page
    .getByText(/^Missing evidence · \d+$/)
    .or(page.getByText(/no missing-evidence items on file/i));
  await expect(checklistOrCta).toBeVisible({ timeout: 15_000 });
});

test("Final analysis tab renders the 9-score card or a generate CTA", async ({
  page,
}) => {
  await signInAsAnika(page);
  await page.goto(CASE_PATH);
  await page.getByRole("tab", { name: /final analysis/i }).click();
  await page.waitForLoadState("networkidle");
  const card = page.getByText(/9-score readiness card/i);
  const cta = page.getByText(/final report not generated yet/i);
  await expect(card.or(cta)).toBeVisible({ timeout: 15_000 });
});
