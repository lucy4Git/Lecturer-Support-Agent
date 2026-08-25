import { expect, Page, test } from "@playwright/test";
import http from "node:http";
import type { AddressInfo } from "node:net";

/**
 * Deterministic coverage of the frontend stream lifecycle (state machine,
 * Stop, partial-response preservation, EOF/malformed-SSE handling, request
 * ownership across conversation switches) against the REAL application
 * code path — not a synthetic showcase page.
 *
 * Real Ollama/provider timing is not controllable enough for deterministic
 * assertions (see the "Ollama post-stop contention" investigation in the
 * accompanying report), so these tests run a tiny local HTTP server that
 * serves genuinely chunked, timing-controlled SSE bodies, and redirect only
 * the `/messages/stream` fetch (via `page.addInitScript` overriding
 * `window.fetch`) to that server. Every other request — login, conversation
 * creation, conversation listing — goes through the real Next.js app and
 * real FastAPI backend. `response.body.getReader()` on the redirected fetch
 * is a genuine ReadableStream over a real chunked HTTP response, so the
 * actual `streamRequest` parser in workspace-shell.tsx is what's under test.
 */

const password = process.env.E2E_DEMO_PASSWORD;
if (!password) {
  test.skip(true, "E2E_DEMO_PASSWORD not set — read from runtime/seed_credentials.txt and export before running E2E tests.");
}

type SseEvent = { type: string; [key: string]: unknown };

function sseFrame(event: SseEvent): string {
  return `data: ${JSON.stringify(event)}\n\n`;
}

const DONE_TEMPLATE = {
  type: "done",
  conversation_id: "mock-conv",
  conversation_title: "Mock conversation",
  user_message_id: "mock-user-msg",
  assistant_message_id: "mock-assistant-msg",
  output_type: "generic_answer",
  title: "Mock title",
  generated_output_id: "mock-output",
  output_version_id: "mock-version",
  version_number: 1,
  workflow_status: "draft",
  risk_level: "none",
  safety_status: "passed",
  requires_human_review: false,
  approval_disclaimer: "",
  integrity_warnings: [],
  pending_action_token: null,
  pending_action_label: "",
  pending_action_details: [],
  sources: [],
};

/** A scripted step: either a real SSE frame, a raw malformed chunk, or a
 * pause before the next write. `close` ends the response without any more
 * data (simulates EOF / dropped connection). */
type MockStep =
  | { frame: SseEvent }
  | { raw: string }
  | { delayMs: number }
  | { close: true };

async function startMockStreamServer(script: MockStep[]): Promise<{ url: string; close: () => Promise<void> }> {
  const server = http.createServer(async (req, res) => {
    if (req.method === "OPTIONS") {
      res.writeHead(204, {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
      });
      res.end();
      return;
    }
    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      Connection: "keep-alive",
    });
    for (const step of script) {
      if ("delayMs" in step) {
        await new Promise((r) => setTimeout(r, step.delayMs));
        continue;
      }
      if ("close" in step) {
        res.end();
        return;
      }
      const chunk = "frame" in step ? sseFrame(step.frame) : step.raw;
      res.write(chunk);
    }
    res.end();
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address() as AddressInfo;
  return {
    url: `http://127.0.0.1:${port}/`,
    close: () => new Promise<void>((resolve) => server.close(() => resolve())),
  };
}

/** Redirects only the app's `/messages/stream` fetch to `targetUrl`, leaving
 * every other request (login, conversation CRUD) untouched and real. */
async function redirectStreamFetchTo(page: Page, targetUrl: string) {
  await page.addInitScript((url) => {
    const originalFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      const href = typeof input === "string" ? input : (input as Request).url;
      if (href.includes("/messages/stream")) {
        return originalFetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, signal: init?.signal ?? undefined });
      }
      return originalFetch(input as any, init);
    };
  }, targetUrl);
}

async function signIn(page: Page) {
  // The backend (127.0.0.1:8000) and the app (localhost:3000) are different
  // origins, so a direct page.request.post to the backend login endpoint
  // sets a cookie the app's origin never receives. Use the app's own
  // same-origin session proxy instead — the same path the real sign-in form
  // uses, and the pattern already proven in runtime/*.mjs scratch checks.
  await page.goto("/sign-in", { waitUntil: "domcontentloaded" });
  const loginResult = await page.evaluate(
    async ([email, pw]) => {
      const resp = await fetch("/api/session/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password: pw, device_label: "Playwright E2E — streaming lifecycle" }),
      });
      return { ok: resp.ok, status: resp.status };
    },
    ["lecturer.demo-north@example.com", password],
  );
  if (!loginResult.ok) throw new Error(`Login API ${loginResult.status}`);
  await page.goto("/");
  await expect(page.locator(".sidebar-new-btn")).toBeVisible({ timeout: 20000 });
}

async function ensureSidebarOpen(page: Page) {
  // On narrow (tablet/mobile) viewports the sidebar starts off-screen behind
  // an "Open navigation" toggle; on desktop it's already visible and this
  // toggle button isn't present at all.
  const opener = page.getByRole("button", { name: "Open navigation" });
  if (await opener.isVisible().catch(() => false)) {
    await opener.click();
    await page.waitForTimeout(200);
  }
}

async function newConversation(page: Page) {
  await ensureSidebarOpen(page);
  await page.locator(".sidebar-new-btn").click();
  await page.waitForTimeout(300);
}

async function sendMessage(page: Page, text: string) {
  const box = page.getByRole("textbox", { name: "Message" });
  await box.click();
  await box.pressSequentially(text, { delay: 5 });
  // Guard against the composer being cleared by an async effect that fires
  // shortly after typing (e.g. a conversation-switch reset); re-type once if
  // the value doesn't stick before asserting Send is enabled.
  try {
    await expect(box).toHaveValue(text, { timeout: 1500 });
  } catch {
    await box.click();
    await box.pressSequentially(text, { delay: 5 });
    await expect(box).toHaveValue(text, { timeout: 3000 });
  }
  await expect(page.getByLabel("Send message")).toBeEnabled({ timeout: 5000 });
  await page.getByLabel("Send message").click();
}

// ── A: normal completion ─────────────────────────────────────────────────
test("normal completion: tokens stream, done received, Stop disappears, actions appear", async ({ page }) => {
  const mock = await startMockStreamServer([
    { frame: { type: "thinking", status: "Generating…" } },
    { frame: { type: "token", text: "Hello" } },
    { frame: { type: "token", text: " world" } },
    { frame: { type: "done", ...DONE_TEMPLATE } },
  ]);
  try {
    await redirectStreamFetchTo(page, mock.url);
    await signIn(page);
    await newConversation(page);
    await sendMessage(page, "test normal completion");

    await expect(page.locator(".stop-button")).toBeVisible({ timeout: 5000 });
    await expect(page.locator(".stop-button")).toBeHidden({ timeout: 10000 });
    await expect(page.getByLabel("Send message")).toBeVisible();

    const assistant = page.locator(".assistant-message").last();
    await expect(assistant).toContainText("Hello world");
    await expect(assistant).toContainText("Copy"); // response actions appeared
  } finally {
    await mock.close();
  }
});

// ── B: Stop preserves partial text, restores composer ──────────────────
test("Stop: partial text retained, interrupted notice shown, Send restored", async ({ page }) => {
  const mock = await startMockStreamServer([
    { frame: { type: "token", text: "Partial content before stop." } },
    { delayMs: 60_000 }, // never completes on its own within the test
  ]);
  try {
    await redirectStreamFetchTo(page, mock.url);
    await signIn(page);
    await newConversation(page);
    await sendMessage(page, "test stop");

    await expect(page.locator(".stop-button")).toBeVisible({ timeout: 5000 });
    await expect(page.locator(".assistant-message")).toContainText("Partial content before stop.", { timeout: 5000 });

    await page.locator(".stop-button").click();

    await expect(page.locator(".stop-button")).toBeHidden({ timeout: 5000 });
    await expect(page.getByLabel("Send message")).toBeVisible();
    const assistant = page.locator(".assistant-message").last();
    await expect(assistant).toContainText("Partial content before stop.");
    await expect(assistant).toContainText("Generation was stopped before it finished.");
  } finally {
    await mock.close();
  }
});

// ── C: double Stop is idempotent ────────────────────────────────────────
test("double Stop: exactly one interrupted assistant message", async ({ page }) => {
  const mock = await startMockStreamServer([
    { frame: { type: "token", text: "Some streamed text." } },
    { delayMs: 60_000 },
  ]);
  try {
    await redirectStreamFetchTo(page, mock.url);
    await signIn(page);
    await newConversation(page);
    await sendMessage(page, "test double stop");

    await expect(page.locator(".assistant-message")).toContainText("Some streamed text.", { timeout: 5000 });
    await page.locator(".stop-button").click();
    // A second click after Stop has already disappeared should be a no-op —
    // click on whatever's now in that slot (Send) rather than erroring.
    await page.waitForTimeout(200);
    if (await page.locator(".stop-button").isVisible().catch(() => false)) {
      await page.locator(".stop-button").click();
    }
    await page.waitForTimeout(300);

    const interrupted = page.locator(".assistant-message", { hasText: "Generation was stopped before it finished." });
    await expect(interrupted).toHaveCount(1);
  } finally {
    await mock.close();
  }
});

// ── D: unexpected EOF (no done, no error frame) ─────────────────────────
test("unexpected EOF: partial text retained, interrupted state, Stop removed", async ({ page }) => {
  const mock = await startMockStreamServer([
    { frame: { type: "token", text: "Text before the connection drops." } },
    { close: true }, // connection ends — no done, no error frame
  ]);
  try {
    await redirectStreamFetchTo(page, mock.url);
    await signIn(page);
    await newConversation(page);
    await sendMessage(page, "test unexpected eof");

    await expect(page.locator(".stop-button")).toBeHidden({ timeout: 10000 });
    await expect(page.getByLabel("Send message")).toBeVisible();
    const assistant = page.locator(".assistant-message").last();
    await expect(assistant).toContainText("Text before the connection drops.");
    await expect(assistant).toContainText("interrupted");
  } finally {
    await mock.close();
  }
});

// ── D2: unexpected EOF with zero tokens ever received ───────────────────
test("unexpected EOF with no tokens: clear notice, optimistic message removed, composer restored", async ({ page }) => {
  const mock = await startMockStreamServer([
    { frame: { type: "thinking", status: "Generating…" } },
    { close: true },
  ]);
  try {
    await redirectStreamFetchTo(page, mock.url);
    await signIn(page);
    await newConversation(page);
    await sendMessage(page, "test empty eof");

    await expect(page.locator(".stop-button")).toBeHidden({ timeout: 10000 });
    await expect(page.getByLabel("Send message")).toBeVisible();
    await expect(page.locator(".conversation-notice")).toContainText("interrupted", { timeout: 5000 });
  } finally {
    await mock.close();
  }
});

// ── E: malformed SSE frame does not crash the workspace ─────────────────
test("malformed SSE: workspace survives, partial content retained, composer usable", async ({ page }) => {
  const mock = await startMockStreamServer([
    { frame: { type: "token", text: "Valid content first." } },
    { raw: "data: {not valid json at all\n\n" },
    { frame: { type: "done", ...DONE_TEMPLATE } },
  ]);
  try {
    await redirectStreamFetchTo(page, mock.url);
    await signIn(page);
    await newConversation(page);
    await sendMessage(page, "test malformed sse");

    // The workspace must not crash: the sidebar and composer remain present.
    await expect(page.locator(".sidebar-new-btn")).toBeVisible({ timeout: 10000 });
    await expect(page.locator(".stop-button")).toBeHidden({ timeout: 10000 });
    await expect(page.getByLabel("Send message")).toBeVisible();
    // The malformed frame is silently ignored (matches the existing
    // try/catch around JSON.parse in the parser); the valid frames around it
    // still land, and the stream reaches its real "done" terminal state.
    await expect(page.locator(".assistant-message").last()).toContainText("Valid content first.");
  } finally {
    await mock.close();
  }
});

// ── E2: malformed frame followed by connection close, no done ever sent ──
test("malformed frame then EOF: partial content retained, reaches interrupted terminal state, never permanent streaming", async ({ page }) => {
  const mock = await startMockStreamServer([
    { frame: { type: "token", text: "Valid text before the break." } },
    { raw: "data: {this is not json and the connection dies right after\n\n" },
    { close: true }, // no done frame ever arrives
  ]);
  try {
    await redirectStreamFetchTo(page, mock.url);
    await signIn(page);
    await newConversation(page);
    await sendMessage(page, "test malformed then eof");

    await expect(page.locator(".sidebar-new-btn")).toBeVisible({ timeout: 10000 });
    await expect(page.locator(".stop-button")).toBeHidden({ timeout: 10000 });
    await expect(page.getByLabel("Send message")).toBeVisible();
    const assistant = page.locator(".assistant-message").last();
    await expect(assistant).toContainText("Valid text before the break.");
    await expect(assistant).toContainText("interrupted");
    // Terminal, not stuck: composer accepts new input immediately.
    await expect(page.getByRole("textbox", { name: "Message" })).toBeEditable();
  } finally {
    await mock.close();
  }
});

// ── E3: malformed JSON as the absolute final frame (nothing after it) ───
test("malformed JSON as final frame: workspace survives, no crash, terminal state reached", async ({ page }) => {
  const mock = await startMockStreamServer([
    { frame: { type: "token", text: "Some real content." } },
    { raw: 'data: {"type":"token","text":\n\n' }, // truncated/invalid JSON, then the socket just ends
  ]);
  try {
    await redirectStreamFetchTo(page, mock.url);
    await signIn(page);
    await newConversation(page);
    await sendMessage(page, "test malformed final frame");

    await expect(page.locator(".sidebar-new-btn")).toBeVisible({ timeout: 10000 });
    await expect(page.locator(".stop-button")).toBeHidden({ timeout: 10000 });
    await expect(page.getByLabel("Send message")).toBeVisible();
    await expect(page.locator(".assistant-message").last()).toContainText("Some real content.");
  } finally {
    await mock.close();
  }
});

// ── Done-exactly-once + duplicate-done safety ────────────────────────────
test("done exactly once: one completion, one assistant message, one set of response actions", async ({ page }) => {
  const mock = await startMockStreamServer([
    { frame: { type: "token", text: "Single completion payload." } },
    { frame: { type: "done", ...DONE_TEMPLATE } },
  ]);
  try {
    await redirectStreamFetchTo(page, mock.url);
    await signIn(page);
    await newConversation(page);
    await sendMessage(page, "test done exactly once");

    await expect(page.locator(".stop-button")).toBeHidden({ timeout: 10000 });
    // Exactly one assistant message was produced by this turn, and it has
    // exactly one set of response actions (Copy appears once, not doubled).
    const assistantMessages = page.locator(".assistant-message", { hasText: "Single completion payload." });
    await expect(assistantMessages).toHaveCount(1);
    const copyActions = page.locator(".assistant-message", { hasText: "Single completion payload." }).getByText("Copy", { exact: true });
    await expect(copyActions).toHaveCount(1);
  } finally {
    await mock.close();
  }
});

test("duplicate done frames: second done is a safe no-op, no duplicate assistant message", async ({ page }) => {
  const mock = await startMockStreamServer([
    { frame: { type: "token", text: "Duplicate-done payload." } },
    { frame: { type: "done", ...DONE_TEMPLATE } },
    { frame: { type: "done", ...DONE_TEMPLATE, assistant_message_id: "mock-assistant-msg-2" } },
  ]);
  try {
    await redirectStreamFetchTo(page, mock.url);
    await signIn(page);
    await newConversation(page);
    await sendMessage(page, "test duplicate done");

    await expect(page.locator(".stop-button")).toBeHidden({ timeout: 10000 });
    await page.waitForTimeout(500); // let any second dispatch, if it fired, land
    const assistantMessages = page.locator(".assistant-message", { hasText: "Duplicate-done payload." });
    await expect(assistantMessages).toHaveCount(1);
    await expect(page.getByLabel("Send message")).toBeVisible();
  } finally {
    await mock.close();
  }
});

// ── H: late token after ownership changes is ignored ────────────────────
test("late token ownership: a frame arriving after New conversation does not leak in", async ({ page }) => {
  const mock = await startMockStreamServer([
    { frame: { type: "token", text: "Owned-by-old-request text." } },
    { delayMs: 2000 },
    { frame: { type: "token", text: "LATE-TOKEN-SHOULD-BE-IGNORED" } },
    { frame: { type: "done", ...DONE_TEMPLATE } },
  ]);
  try {
    await redirectStreamFetchTo(page, mock.url);
    await signIn(page);
    await newConversation(page);
    await sendMessage(page, "test late token ownership");
    await expect(page.locator(".assistant-message")).toContainText("Owned-by-old-request text.", { timeout: 5000 });

    // Abandon this request before the late token arrives.
    await ensureSidebarOpen(page);
    await page.locator(".sidebar-new-btn").click();
    await page.waitForTimeout(2500); // let the late frame's window pass

    // The new, empty conversation must never show the late token.
    await expect(page.locator("body")).not.toContainText("LATE-TOKEN-SHOULD-BE-IGNORED");
    await expect(page.getByRole("textbox", { name: "Message" })).toHaveValue("");
  } finally {
    await mock.close();
  }
});

// ── F: switch conversation during an active stream ──────────────────────
test("switch conversation during stream: no late token leaks into the newly opened conversation", async ({ page }) => {
  const mock = await startMockStreamServer([
    { frame: { type: "token", text: "Conversation A partial text." } },
    { delayMs: 2000 },
    { frame: { type: "token", text: "A-LATE-TOKEN-AFTER-SWITCH" } },
    { frame: { type: "done", ...DONE_TEMPLATE } },
  ]);
  try {
    await redirectStreamFetchTo(page, mock.url);
    await signIn(page);
    await newConversation(page);
    await sendMessage(page, "conversation A streaming test");
    await expect(page.locator(".assistant-message")).toContainText("Conversation A partial text.", { timeout: 5000 });

    // Start a new conversation while A's stream is still in flight — this
    // must abort A's stream via the request-ownership check (same mechanism
    // proven by the "late token ownership" case above, exercised here mid-
    // stream instead of after a Stop).
    await ensureSidebarOpen(page);
    await page.locator(".sidebar-new-btn").click();
    await expect(page.getByText("What would you like to work on?")).toBeVisible({ timeout: 5000 });
    await page.waitForTimeout(3000); // let the mock's delayed late frame's window pass

    await expect(page.locator("body")).not.toContainText("A-LATE-TOKEN-AFTER-SWITCH");
  } finally {
    await mock.close();
  }
});
