import { expect, test, type Page } from "@playwright/test";

/**
 * E2E smoke pass for the full lawyer workspace.
 * Assumes:
 *   - uvicorn  on http://127.0.0.1:8000  (FastAPI shim)
 *   - next dev on http://localhost:3000  (this frontend)
 *   - demo users seeded via `python -m core.db`
 */

async function signInAsAnika(page: Page) {
  await page.goto("/login");
  // The auth card lives on the right; the demo cards on the left.
  // Demo button label is exactly "Sign in as Anika".
  await page.getByRole("button", { name: "Sign in as Anika" }).click();
  // Landing target is /dashboard for users with a profile already set up.
  await page.waitForURL("**/dashboard", { timeout: 10_000 });
}

test.beforeEach(async ({ context }) => {
  await context.clearCookies();
});

test("landing page renders with both demo cards visible", async ({ page }) => {
  await page.goto("/login");
  await expect(
    page.getByRole("heading", { name: /the case file/i }),
  ).toBeVisible();
  await expect(page.getByText("Anika Rao")).toBeVisible();
  await expect(page.getByText("Vikram Shastri")).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in as Anika" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Sign in as Vikram" })).toBeEnabled();
});

test("root route redirects to /login when unauthenticated", async ({ page }) => {
  await page.goto("/");
  await page.waitForURL("**/login");
  expect(page.url()).toContain("/login");
});

test("workspace route redirects to /login when unauthenticated", async ({ page }) => {
  // server-side guard in (workspace)/layout.tsx checks for the cookie
  await page.goto("/dashboard");
  await page.waitForURL("**/login");
});

test("demo login as Anika lands on dashboard with seeded data", async ({ page }) => {
  await signInAsAnika(page);
  await expect(page.getByRole("heading", { name: /good day, anika/i })).toBeVisible();
  // Pre-loaded case from the seed
  await expect(
    page.getByRole("heading", {
      name: /aurelia ventures pvt ltd v\. stellar holdings llp/i,
    }),
  ).toBeVisible();
  // Stat cards present
  await expect(page.getByText("Active cases", { exact: true })).toBeVisible();
});

test("demo login as Vikram lands on dashboard with his seeded case", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in as Vikram" }).click();
  await page.waitForURL("**/dashboard");
  await expect(page.getByRole("heading", { name: /good day, vikram/i })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: /ravi menon v\. state of maharashtra/i }),
  ).toBeVisible();
});

test("opening a case shows the detail page with parties and key dates", async ({ page }) => {
  await signInAsAnika(page);
  await page.getByRole("link", { name: /open case aurelia/i }).click();
  await page.waitForURL("**/cases/1");
  await expect(
    page.getByRole("heading", {
      name: /aurelia ventures pvt ltd v\. stellar holdings llp/i,
    }),
  ).toBeVisible();
  // Eyebrow with court name
  await expect(page.getByText("Bombay High Court").first()).toBeVisible();
  // Case workspace list mentions live and coming packages
  await expect(page.getByText("Evidence Vault", { exact: true })).toBeVisible();
  await expect(page.getByText("Research & Precedent Engine")).toBeVisible();
});

test("navigating to the evidence vault shows the ingested document", async ({ page }) => {
  await signInAsAnika(page);
  await page.goto("/cases/1/evidence");
  await expect(page.getByRole("heading", { name: /aurelia ventures/i })).toBeVisible();
  // The default tab is Upload & ingest; the right column lists existing docs.
  await expect(page.getByText("aurelia_v_stellar.pdf")).toBeVisible();
  await expect(page.getByText("Plaint excerpt — Aurelia v. Stellar")).toBeVisible();
  await expect(page.getByText("completed", { exact: true })).toBeVisible();
});

test("evidence chat returns a cited answer (fallback synthesiser)", async ({ page }) => {
  await signInAsAnika(page);
  await page.goto("/cases/1/evidence");
  await page.getByRole("tab", { name: /evidence chat/i }).click();
  // Start from a known clean slate — the case may have prior chat history.
  const clear = page.getByRole("button", { name: /clear/i });
  if (await clear.isEnabled()) {
    await clear.click();
  }
  // Empty state is now visible
  await expect(page.getByText(/ask the case anything/i)).toBeVisible();
  // Type a question and submit
  const composer = page.getByPlaceholder(/ask a question about this case/i);
  const QUESTION = "What is the strongest evidence?";
  await composer.fill(QUESTION);
  await composer.press("Enter");
  // The user turn we just sent appears
  await expect(page.getByText(QUESTION, { exact: true })).toBeVisible({ timeout: 15_000 });
  // An assistant turn arrives (labelled "Glimmora") with cited sources
  await expect(page.getByText("Glimmora", { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/last answer ·/i)).toBeVisible();
  // Empty state should be gone
  await expect(page.getByText(/ask the case anything/i)).not.toBeVisible();
});

test("simulator, copilot, report placeholder pages render", async ({ page }) => {
  // Note: /cases/{id}/research is no longer a placeholder — that route now
  // hosts the full Research & Precedent Engine UI (see research-tabs.spec.ts).
  await signInAsAnika(page);
  for (const [path, heading] of [
    ["/cases/1/simulator", /case study simulator/i],
    ["/cases/1/copilot", /lawyer copilot workspace/i],
    ["/cases/1/report", /final case intelligence report/i],
  ] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    await expect(page.getByRole("link", { name: /back to case/i })).toBeVisible();
  }
});

test("creating a case is reachable from the dashboard", async ({ page }) => {
  await signInAsAnika(page);
  await page.getByRole("link", { name: /new case/i }).click();
  await page.waitForURL("**/cases/new");
  await expect(page.getByRole("heading", { name: /open a new case/i })).toBeVisible();
  await expect(page.getByLabel(/case name/i)).toBeVisible();
});

test("sign out returns to the login page", async ({ page }) => {
  await signInAsAnika(page);
  await page.getByRole("button", { name: /sign out/i }).click();
  await page.waitForURL("**/login");
  // And the cookie is cleared — root should now redirect to /login too
  await page.goto("/");
  await page.waitForURL("**/login");
});
