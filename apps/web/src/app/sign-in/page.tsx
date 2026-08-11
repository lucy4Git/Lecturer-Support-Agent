"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

type AvailableRole = {
  role_code: string;
  role_name: string;
  role_assignment_id: string;
};

type AvailableInstitution = {
  id: string;
  display_name: string;
  institution_type: string;
};

export default function SignInPage() {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [availableRoles, setAvailableRoles] = useState<AvailableRole[]>([]);
  const [availableInstitutions, setAvailableInstitutions] = useState<AvailableInstitution[]>([]);
  const [mfaRequired, setMfaRequired] = useState(false);
  const [selectedInstitutionId, setSelectedInstitutionId] = useState<string | null>(null);

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
    if (values.get("role_code")) body.role_code = values.get("role_code");
    if (values.get("mfa_code")) body.mfa_code = values.get("mfa_code");
    if (selectedInstitutionId) body.institution_id = selectedInstitutionId;
    if (values.get("institution_id")) body.institution_id = values.get("institution_id");

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
    if (response.status === 428 && detail?.code === "mfa_required") {
      setMfaRequired(true);
      setMessage("Enter the code from your authenticator app, then sign in again.");
    } else if (response.status === 409 && Array.isArray(detail?.available_roles)) {
      setAvailableRoles(detail.available_roles as AvailableRole[]);
      setMessage("You have multiple roles. Choose which role to use for this session.");
    } else if (response.status === 409 && Array.isArray(detail?.available_institutions)) {
      setAvailableInstitutions(detail.available_institutions as AvailableInstitution[]);
      setMessage("Your account belongs to multiple institutions. Please select one below.");
    } else {
      setMessage(typeof detail === "string" ? detail : detail?.message ?? "Sign-in failed.");
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

          {mfaRequired && (
            <label>
              <span>Authenticator or recovery code</span>
              <input name="mfa_code" autoComplete="one-time-code" inputMode="numeric" required />
            </label>
          )}

          {availableRoles.length > 0 && (
            <label>
              <span>Role for this session</span>
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

          {availableInstitutions.length > 0 && (
            <label>
              <span>Select your institution</span>
              <select
                name="institution_id"
                required
                defaultValue=""
                onChange={(e) => setSelectedInstitutionId(e.target.value)}
              >
                <option value="" disabled>Select an institution</option>
                {availableInstitutions.map((inst) => (
                  <option key={inst.id} value={inst.id}>
                    {inst.display_name}
                  </option>
                ))}
              </select>
            </label>
          )}

          {message && (
            <div className={availableRoles.length || availableInstitutions.length ? "notice" : "error-notice"}>
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
