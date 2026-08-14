"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

type AvailableRole = {
  role_code: string;
  role_name: string;
  role_assignment_id: string;
};

type InstitutionContext = {
  institution_id: string;
  institution_display_name: string;
  institution_type: string;
  role_code: string;
  role_name: string;
  role_assignment_id: string;
};

export default function SignInPage() {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [availableRoles, setAvailableRoles] = useState<AvailableRole[]>([]);
  const [availableContexts, setAvailableContexts] = useState<InstitutionContext[]>([]);

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

    // Single-institution role selection (same institution, multiple roles)
    const selectedRole = values.get("role_code");
    if (selectedRole) body.role_code = selectedRole;

    // Multi-institution context selection
    const selectedContext = values.get("context_key");
    if (selectedContext && availableContexts.length > 0) {
      const [institutionId, roleCode] = (selectedContext as string).split("|");
      body.institution_id = institutionId;
      body.role_code = roleCode;
    }

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
    if (response.status === 409 && detail?.context_selection_required) {
      // Multi-institution: user has active memberships at more than one institution
      setAvailableContexts(detail.available_contexts as InstitutionContext[]);
      setAvailableRoles([]);
      setMessage("Your account is active at multiple institutions. Select the institution and role to use.");
    } else if (response.status === 409 && Array.isArray(detail?.available_roles)) {
      // Single institution, multiple roles
      setAvailableRoles(detail.available_roles as AvailableRole[]);
      setAvailableContexts([]);
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

          {availableContexts.length > 0 && (
            <label>
              <span>Institution and role</span>
              <select name="context_key" required defaultValue="">
                <option value="" disabled>Select institution and role</option>
                {availableContexts.map((ctx) => (
                  <option
                    key={ctx.role_assignment_id}
                    value={`${ctx.institution_id}|${ctx.role_code}`}
                  >
                    {ctx.institution_display_name} — {ctx.role_name}
                  </option>
                ))}
              </select>
            </label>
          )}

          {availableRoles.length > 0 && availableContexts.length === 0 && (
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
            <div className={availableRoles.length || availableContexts.length ? "notice" : "error-notice"}>
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
