import { expect, Page, test } from "@playwright/test";

const password = process.env.E2E_DEMO_PASSWORD;
if (!password) {
  test.skip(true, "E2E_DEMO_PASSWORD not set — read from runtime/seed_credentials.txt and export before running E2E tests.");
}

async function signIn(page: Page, handle: string, role: string) {
  await page.goto("/sign-in");
  await page.getByLabel("Institution code").fill("demo-north");
  await page.getByLabel("Email").fill(`${handle}@demo-north.example.invalid`);
  await page.getByLabel("Password").fill(password);
  await page.getByLabel("Role code (only when already known)").fill(role);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/$/);
}

test("institution administrator sees governed commercial controls", async ({ page }) => {
  await signIn(page, "admin", "institution_administrator");
  for (const label of ["Insights", "Reports", "Audit centre", "Platform settings"]) {
    await expect(page.getByRole("button", { name: new RegExp(label, "i") })).toBeVisible();
  }
  await page.getByRole("button", { name: /Audit centre/i }).click();
  await expect(page.getByRole("heading", { name: "Audit centre" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Export JSON" })).toBeVisible();
});

test("lecturer receives personal insights without administrator controls", async ({ page }) => {
  await signIn(page, "lecturer", "lecturer");
  await expect(page.getByRole("button", { name: /Insights/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /Reports/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /Audit centre/i })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Platform settings/i })).toHaveCount(0);
  await page.getByRole("button", { name: /Insights/i }).click();
  await expect(page.getByRole("heading", { name: "Insights" })).toBeVisible();
});

test("head of department keeps scoped analytics separate from institution administration", async ({ page }) => {
  await signIn(page, "hod", "head_of_department");
  await expect(page.getByRole("button", { name: /Insights/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /Reports/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /Audit centre/i })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Platform settings/i })).toHaveCount(0);
  await page.getByRole("button", { name: /Insights/i }).click();
  await expect(page.getByLabel("Authorised academic-unit ID")).toBeVisible();
});
