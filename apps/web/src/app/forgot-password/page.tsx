"use client";

import Link from "next/link";
import { FormEvent, useRef, useState } from "react";

export default function ForgotPasswordPage() {
  const [message, setMessage] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    setIsError(false);
    const values = new FormData(event.currentTarget);
    const newPassword = values.get("new_password") as string;
    const confirmPassword = values.get("confirm_password") as string;
    if (newPassword !== confirmPassword) {
      setIsError(true);
      setMessage("Passwords do not match.");
      setBusy(false);
      return;
    }
    const response = await fetch("/api/session/direct-reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: values.get("email"),
        new_password: newPassword,
        confirm_password: confirmPassword,
      }),
    });
    if (response.ok || response.status === 204) {
      setDone(true);
      setMessage("Password changed. You can now sign in with your new password.");
    } else {
      const data = await response.json().catch(() => ({}));
      setIsError(true);
      const detail = data?.detail;
      // 503 = Vercel proxy waiting for Railway cold-start; surface the server's
      // specific message so the user knows to retry rather than re-enter data.
      setMessage(typeof detail === "string" ? detail : "The password could not be changed.");
    }
    setBusy(false);
  }

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
              <input type="password" name="confirm_password" autoComplete="new-password" required />
            </label>
            {message && <div className={isError ? "error-notice" : "notice"}>{message}</div>}
            <button className="submit-button" disabled={busy}>
              {busy ? "Changing password…" : "Change password"}
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
