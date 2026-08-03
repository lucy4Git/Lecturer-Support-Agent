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

async function signIn(page: Page, handle: string, role: string) {
  await page.goto("/sign-in");
  await page.getByLabel("Institution code").fill("demo-north");
  await page.getByLabel("Email").fill(`${handle}@demo-north.example.invalid`);
  await page.getByLabel("Password").fill(password);
  await page.getByLabel("Role code (only when already known)").fill(role);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("button", { name: /New conversation/i })).toBeVisible();
}

test("public sign-in is usable and responsive", async ({ page }) => {
  await page.goto("/sign-in");
  await expect(page.getByRole("heading", { name: "Sign in to your institution" })).toBeVisible();
  await expect(page.getByLabel("Institution code")).toBeVisible();
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
  await screenshot(page, "public-sign-in");
});

for (const scenario of [
  { handle: "admin", role: "institution_administrator", label: "Institution Administrator", action: "Invite user" },
  { handle: "hod", role: "head_of_department", label: "Head of Department", action: "Teaching operations" },
  { handle: "lecturer", role: "lecturer", label: "Lecturer", action: "My teaching plans" },
  { handle: "moderator", role: "internal_moderator", label: "Internal Moderator", action: "Review tasks" },
  { handle: "external", role: "external_reviewer", label: "External Reviewer", action: "Review tasks" },
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
