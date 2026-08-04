"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

type AvailableRole = {
  role_code: string;
  role_name: string;
  role_assignment_id: string;
  scope_type?: string | null;
  scope_id?: string | null;
};

export default function SignInPage() {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [availableRoles, setAvailableRoles] = useState<AvailableRole[]>([]);
  const [mfaRequired, setMfaRequired] = useState(false);
  const [ssoBusy, setSsoBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    const values = new FormData(event.currentTarget);
    const response = await fetch("/api/session/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: values.get("email"),
        password: values.get("password"),
        institution_slug: values.get("institution_slug"),
        role_code: values.get("role_code") || null,
        device_label: "Web browser",
        mfa_code: values.get("mfa_code") || null,
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (response.ok) {
      router.replace("/");
      router.refresh();
      return;
    }
    const detail = data.detail;
    if (response.status === 428 && detail?.code === "mfa_required") {
      setMfaRequired(true);
      setMessage("Enter the code from your authenticator app or a recovery code, then sign in again.");
    } else if (response.status === 409 && Array.isArray(detail?.available_roles)) {
      setAvailableRoles(detail.available_roles as AvailableRole[]);
      setMessage("Choose the role you want to use for this session, then sign in again.");
    } else {
      setMessage(typeof detail === "string" ? detail : detail?.message ?? "Sign-in failed.");
    }
    setBusy(false);
  }


  async function startSSO(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSsoBusy(true); setMessage(null);
    const values = new FormData(event.currentTarget);
    const response = await fetch("/api/session/sso/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ institution_slug: values.get("sso_institution_slug"), connection_code: values.get("connection_code"), redirect_uri: `${window.location.origin}/sso/callback` }),
    });
    const data = await response.json().catch(() => ({}));
    if (response.ok && data.authorization_url) { window.location.assign(data.authorization_url); return; }
    setMessage(typeof data.detail === "string" ? data.detail : "Institution SSO could not be started."); setSsoBusy(false);
  }

  return (
    <main id="main-content" className="auth-page">
      <section className="auth-card">
        <div className="brand-mark">LS</div>
        <span className="eyebrow">Lecturer Support Agent</span>
        <h1>Sign in to your institution</h1>
        <p>Use your institution, account, and one active system role. Roles remain independent for each session.</p>
        <form onSubmit={submit}>
          <label><span>Institution code</span><input name="institution_slug" required /></label>
          <label><span>Email</span><input name="email" type="email" required /></label>
          <label><span>Password</span><input name="password" type="password" required /></label>
          {mfaRequired && <label><span>Authenticator or recovery code</span><input name="mfa_code" autoComplete="one-time-code" required /></label>}
          {availableRoles.length > 0 ? (
            <label>
              <span>Active role for this session</span>
              <select name="role_code" required defaultValue="">
                <option value="" disabled>Select a role</option>
                {availableRoles.map((role) => (
                  <option key={role.role_assignment_id} value={role.role_code}>
                    {role.role_name}{role.scope_type ? ` — ${role.scope_type}` : ""}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label><span>Role code (only when already known)</span><input name="role_code" /></label>
          )}
          {message && <div className={availableRoles.length ? "notice" : "error-notice"}>{message}</div>}
          <button className="submit-button" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
          <Link href="/forgot-password" className="link-button">Forgot password?</Link>
          <Link href="/accept-invitation" className="link-button">Have an invitation? Accept it</Link>
          <Link href="/request-access" className="link-button">Need access? Request institutional access</Link>
        </form>
        <div className="auth-divider"><span>or use institution SSO</span></div>
        <form onSubmit={startSSO}>
          <label><span>Institution code</span><input name="sso_institution_slug" required /></label>
          <label><span>SSO connection code</span><input name="connection_code" placeholder="e.g. microsoft-entra" required /></label>
          <button className="secondary-button" disabled={ssoBusy}>{ssoBusy ? "Redirecting…" : "Continue with SSO"}</button>
        </form>
      </section>
    </main>
  );
}
