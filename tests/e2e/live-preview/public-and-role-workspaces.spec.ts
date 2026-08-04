import { expect, Page, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const evidenceRoot = process.env.VALIDATION_EVIDENCE_DIR;
const password = process.env.E2E_DEMO_PASSWORD;
if (!password) {
  test.skip(true, "E2E_DEMO_PASSWORD not set — read from runtime/seed_credentials.txt and export before running E2E tests.");
}

async function screenshot(page: Page, name: string) {
  if (!evidenceRoot) return;
  const directory = path.join(evidenceRoot, "screenshots");
  fs.mkdirSync(directory, { recursive: true });
  await page.screenshot({ path: path.join(directory, `${test.info().project.name}-${name}.png`), fullPage: true });
}

// Authenticate via the API directly — bypasses Playwright vs dev-server hydration
// timing issues. The API sets HTTP-only cookies that Playwright's cookie jar stores,
// so subsequent page.goto calls are authenticated.
async function signIn(page: Page, handle: string, role: string) {
  const baseUrl = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000";
  const apiUrl = process.env.E2E_API_URL ?? "http://127.0.0.1:8000";
  const resp = await page.request.post(`${apiUrl}/api/v1/auth/login`, {
    data: {
      institution_slug: "demo-north",
      email: `${handle}.demo-north@example.com`,
      password,
      role_code: role,
      device_label: "Playwright E2E",
    },
  });
  if (!resp.ok()) {
    const body = await resp.text().catch(() => "(no body)");
    throw new Error(`Login API returned ${resp.status()} for ${handle}/${role}: ${body}`);
  }
  // Navigate to the home page; cookies from the API response are already stored.
  await page.goto(`${baseUrl}/`);
  await expect(page.getByRole("button", { name: /New conversation/i })).toBeVisible({ timeout: 20000 });
}

test("public sign-in is usable and responsive", async ({ page }) => {
  await page.goto("/sign-in");
  await page.waitForLoadState("domcontentloaded");
  await expect(page.getByRole("heading", { name: "Sign in to your institution" })).toBeVisible();
  await expect(page.locator('input[name="institution_slug"]').first()).toBeVisible();
  await expect(page.locator('input[name="email"]').first()).toBeVisible();
  await expect(page.locator('input[name="password"]').first()).toBeVisible();
  await screenshot(page, "public-sign-in");
});

for (const scenario of [
  { handle: "admin", role: "institution_administrator", label: "Institution Administrator", action: "Invite user" },
  { handle: "hod", role: "head_of_department", label: "Head of Department", action: "Teaching operations" },
  { handle: "lecturer", role: "lecturer", label: "Lecturer", action: "My teaching plans" },
  { handle: "moderator", role: "internal_moderator", label: "Internal Moderator", action: "Review tasks" },
  { handle: "external", role: "external_reviewer", label: "External Reviewer", action: "Review tasks" },
  { handle: "modcoord", role: "module_coordinator", label: "Module Coordinator", action: "Teaching operations" },
  { handle: "progcoord", role: "programme_coordinator", label: "Programme Coordinator", action: "Teaching operations" },
  { handle: "extmod", role: "external_moderator", label: "External Moderator", action: "Review tasks" },
]) {
  test(`${scenario.label} sees only the intended contextual workspace actions`, async ({ page }) => {
    await signIn(page, scenario.handle, scenario.role);
    const roleLabel = page.getByText(scenario.label, { exact: true });
    let openedMobileNavigation = false;
    if (!(await roleLabel.isVisible())) {
      await page.getByRole("button", { name: "Open conversation navigation" }).click();
      openedMobileNavigation = true;
    }
    await expect(roleLabel).toBeVisible();
    if (openedMobileNavigation) {
      await page.getByRole("button", { name: "Open conversation navigation" }).click();
      await expect(roleLabel).not.toBeVisible();
    }
    await expect(page.getByPlaceholder("Message Lecturer Support Agent")).toBeVisible();
    await page.getByRole("button", { name: "Role actions" }).click();
    await expect(page.getByText(scenario.action, { exact: true })).toBeVisible();
    if (scenario.role === "head_of_department") await expect(page.getByText("Invite user", { exact: true })).toHaveCount(0);
    if (scenario.role === "institution_administrator") await expect(page.getByText("Assign lecturer", { exact: true })).toHaveCount(0);
    await screenshot(page, scenario.role);
  });
}


test("lecturer completes a unified inline teaching-output request", async ({ page }) => {
  await signIn(page, "lecturer", "lecturer");
  const prompt = "Generate a 30-minute practical lesson on IoT sensors for diploma students.";
  await page.getByPlaceholder("Message Lecturer Support Agent").fill(prompt);
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(prompt, { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Draft teaching support output" })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Version 1", { exact: true })).toBeVisible();
  await expect(page.getByText(/Human review is required before formal teaching or assessment use/i)).toBeVisible();
  await screenshot(page, "lecturer-unified-output");
});
