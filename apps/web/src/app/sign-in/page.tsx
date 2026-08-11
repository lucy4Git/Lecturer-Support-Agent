"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

type AvailableRole = {
  role_code: string;
  role_name: string;
  role_assignment_id: string;
};

export default function SignInPage() {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [availableRoles, setAvailableRoles] = useState<AvailableRole[]>([]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    const values = new FormData(event.currentTarget);

    const body: Record<string, unknown> = {
      email: values.get("email"),
      password: values.get("password"),
      device_label: "Web browser",
    };
    const selectedRole = values.get("role_code");
    if (selectedRole) body.role_code = selectedRole;

    const response = await fetch("/api/session/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));

    if (response.ok) {
      router.replace("/");
      router.refresh();
      return;
    }

    const detail = data.detail;
    if (response.status === 409 && Array.isArray(detail?.available_roles)) {
      setAvailableRoles(detail.available_roles as AvailableRole[]);
      setMessage("You have more than one active role. Choose the role for this session.");
    } else {
      setMessage(typeof detail === "string" ? detail : detail?.message ?? "Sign-in failed. Check your email and password.");
    }
    setBusy(false);
  }

  return (
    <main id="main-content" className="auth-page">
      <section className="auth-card">
        <div className="brand-mark">LS</div>
        <span className="eyebrow">Lecturer Support Agent</span>
        <h1>Sign in</h1>
        <p>Enter your institution email and password to continue.</p>
        <form onSubmit={submit}>
          <label>
            <span>Institution email</span>
            <input name="email" type="email" autoComplete="email" required />
          </label>
          <label>
            <span>Password</span>
            <input name="password" type="password" autoComplete="current-password" required />
          </label>

          {availableRoles.length > 0 && (
            <label>
              <span>Continue as</span>
              <select name="role_code" required defaultValue="">
                <option value="" disabled>Select a role</option>
                {availableRoles.map((role) => (
                  <option key={role.role_assignment_id} value={role.role_code}>
                    {role.role_name}
                  </option>
                ))}
              </select>
            </label>
          )}

          {message && (
            <div className={availableRoles.length ? "notice" : "error-notice"}>
              {message}
            </div>
          )}

          <button className="submit-button" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <Link href="/forgot-password" className="link-button">Forgot password?</Link>
          <Link href="/sign-up" className="link-button">Create an account</Link>
        </form>
      </section>
    </main>
  );
}
