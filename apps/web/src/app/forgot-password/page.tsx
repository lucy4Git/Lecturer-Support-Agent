"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";

// Warm-up timeout: stop blocking the form after this many ms even if the
// ping is still running.  15 s is enough for Neon to wake from cold.
const WARM_UP_TIMEOUT_MS = 15_000;

export default function ForgotPasswordPage() {
  const [message, setMessage]   = useState<string | null>(null);
  const [isError, setIsError]   = useState(false);
  const [busy, setBusy]         = useState(false);
  const [done, setDone]         = useState(false);
  // True while the warm-up ping is in flight; form is disabled until resolved.
  const [warming, setWarming]   = useState(true);
  const formRef = useRef<HTMLFormElement>(null);

  // Warm Railway + Neon before the user can submit.  The form stays disabled
  // until the ping resolves or WARM_UP_TIMEOUT_MS elapses — whichever comes
  // first.  This prevents the reset POST from racing a cold Neon startup.
  useEffect(() => {
    let cancelled = false;
    const timeout = setTimeout(() => {
      if (!cancelled) setWarming(false);
    }, WARM_UP_TIMEOUT_MS);

    fetch("/api/session/ping")
      .catch(() => undefined)
      .finally(() => {
        clearTimeout(timeout);
        if (!cancelled) setWarming(false);
      });

    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    setIsError(false);

    const values = new FormData(event.currentTarget);
    const newPassword     = values.get("new_password") as string;
    const confirmPassword = values.get("confirm_password") as string;

    if (newPassword !== confirmPassword) {
      setIsError(true);
      setMessage("Passwords do not match.");
      setBusy(false);
      return;
    }

    let response: Response;
    try {
      response = await fetch("/api/session/direct-reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: values.get("email"),
          new_password: newPassword,
          confirm_password: confirmPassword,
        }),
      });
    } catch {
      setIsError(true);
      setMessage("Could not reach the server. Check your connection and try again.");
      setBusy(false);
      return;
    }

    if (response.ok || response.status === 204) {
      setDone(true);
      setMessage("Password changed. You can now sign in with your new password.");
    } else {
      const data = await response.json().catch(() => ({}));
      setIsError(true);
      const detail = data?.detail;
      setMessage(typeof detail === "string" ? detail : "The password could not be changed.");
    }
    setBusy(false);
  }

  const buttonDisabled = busy || warming;
  const buttonLabel = warming
    ? "Preparing…"
    : busy
    ? "Changing password…"
    : "Change password";

  return (
    <main id="main-content" className="auth-page">
      <section className="auth-card">
        <div className="brand-mark">LS</div>
        <span className="eyebrow">Account recovery</span>
        <h1>Change your password</h1>
        <p>Enter your email and choose a new password.</p>
        {!done ? (
          <form ref={formRef} onSubmit={submit}>
            <label>
              <span>Email</span>
              <input type="email" name="email" autoComplete="email" required />
            </label>
            <label>
              <span>New password</span>
              <input type="password" name="new_password" autoComplete="new-password" required />
            </label>
            <label>
              <span>Confirm new password</span>
              <input
                type="password"
                name="confirm_password"
                autoComplete="new-password"
                required
              />
            </label>
            {message && (
              <div className={isError ? "error-notice" : "notice"}>{message}</div>
            )}
            <button className="submit-button" disabled={buttonDisabled}>
              {buttonLabel}
            </button>
          </form>
        ) : (
          <div className="notice">{message}</div>
        )}
        <Link href="/sign-in" className="link-button">Return to sign in</Link>
      </section>
    </main>
  );
}
