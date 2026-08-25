import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "../../tests/e2e/live-preview",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  // Deliberate, not a default oversight: running the desktop/tablet/mobile
  // projects as separate concurrent workers (Playwright's default) produced
  // 33/36 and 35/36 flaky results in this environment across repeated runs,
  // against a reliable 36/36 with workers=1. The suite logs in with one
  // shared seeded demo account and drives one shared local dev backend —
  // concurrent workers create real contention on that single account/server,
  // not a bug in the tests themselves. Isolating every test behind its own
  // tenant/account would remove this ceiling, but is out of scope for this
  // change; until then, serial execution is the supported configuration so
  // that the plain `npm run test:e2e` command is reliably green.
  workers: 1,
  reporter: [["list"], ["html", { outputFolder: "../../runtime/validation/playwright-report", open: "never" }]],
  use: {
    // 127.0.0.1 trips Next dev's origin/host protection (blocked HMR
    // websocket + 403s on internal assets), which silently breaks React
    // hydration on the workspace page — the composer looks fine on screen
    // but stops responding to input. localhost is the correct default.
    //
    // Port 3000 is also used by an unrelated project on shared dev
    // machines and can be raced away from this app without warning
    // (confirmed: `next dev` silently serves whichever app's server won
    // the race, with no error). Prefer running this app's dev server on
    // a dedicated port via `E2E_BASE_URL` (e.g. `npx next dev -p 3100`)
    // when port 3000 is not exclusively this project's.
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } } },
    { name: "tablet", use: { ...devices["iPad Pro 11"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
});
