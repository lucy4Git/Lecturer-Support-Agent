import { expect, Page, test } from "@playwright/test";

const password = process.env.E2E_DEMO_PASSWORD;
if (!password) {
  test.skip(true, "E2E_DEMO_PASSWORD not set — read from runtime/seed_credentials.txt and export before running E2E tests.");
}

async function signIn(page: Page, handle = "lecturer", role = "lecturer") {
  await page.goto("/sign-in");
  await page.getByLabel("Institution code").fill("demo-north");
  await page.getByLabel("Email").fill(`${handle}@demo-north.example.invalid`);
  await page.getByLabel("Password").fill(password);
  await page.getByLabel("Role code (only when already known)").fill(role);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/$/);
}

test("commercial workspace exposes unified resource navigation", async ({ page }) => {
  await signIn(page);
  for (const label of ["Search", "Library", "Files", "Saved outputs", "Notifications"]) {
    await expect(page.getByRole("button", { name: new RegExp(label, "i") })).toBeVisible();
  }
  await page.getByRole("button", { name: /Search/i }).click();
  await expect(page.getByRole("heading", { name: "Search" })).toBeVisible();
  await expect(page.getByLabel("Search workspace")).toBeVisible();
});

test("library stays in the unified shell and can attach a version", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: /Library/i }).click();
  await expect(page.getByRole("heading", { name: "Library" })).toBeVisible();
  const attach = page.getByRole("button", { name: "Attach to conversation" }).first();
  if (await attach.count()) {
    await attach.click();
    await expect(page.getByPlaceholder("Message Lecturer Support Agent")).toBeVisible();
  }
});

test("keyboard search and appearance control remain available", async ({ page }) => {
  await signIn(page);
  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  await expect(page.getByRole("heading", { name: "Search" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Use dark appearance|Use light appearance/ })).toBeVisible();
});
