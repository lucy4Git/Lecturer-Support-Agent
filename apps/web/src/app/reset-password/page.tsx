"use client";

import { FormEvent, Suspense, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";

function ResetPasswordForm() {
  const params = useSearchParams();
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const values = new FormData(event.currentTarget);
    if (values.get("password") !== values.get("confirmation")) {
      setMessage("Passwords do not match.");
      setBusy(false);
      return;
    }
    const response = await fetch("/api/session/password-reset/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reset_token: params.get("token"),
        new_password: values.get("password"),
      }),
    });
    if (response.ok) {
      router.replace("/sign-in?reset=1");
      return;
    }
    const data = await response.json().catch(() => ({}));
    setMessage(data.detail || "The token is invalid or expired.");
    setBusy(false);
  }

  return (
    <form onSubmit={submit}>
      <label>
        <span>New password</span>
        <input type="password" name="password" minLength={12} required />
      </label>
      <label>
        <span>Confirm password</span>
        <input type="password" name="confirmation" minLength={12} required />
      </label>
      {message && <div className="error-notice">{message}</div>}
      <button className="submit-button" disabled={busy || !params.get("token")}>
        {busy ? "Updating…" : "Update password"}
      </button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <main className="auth-page">
      <section className="auth-card">
        <div className="brand-mark">LS</div>
        <span className="eyebrow">Secure account recovery</span>
        <h1>Choose a new password</h1>
        <Suspense fallback={<p>Loading&hellip;</p>}>
          <ResetPasswordForm />
        </Suspense>
      </section>
    </main>
  );
}
