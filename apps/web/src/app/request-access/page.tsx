"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

export default function RequestAccessPage() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    const values = new FormData(event.currentTarget);
    const response = await fetch("/api/session/access-request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        institution_slug: values.get("institution_slug"),
        email: values.get("email"),
        given_name: values.get("given_name"),
        family_name: values.get("family_name"),
        position_title: values.get("position_title") || null,
        requested_role_code: values.get("requested_role_code") || null,
        request_message: values.get("request_message") || null,
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (response.ok) {
      setSubmitted(true);
      setMessage(data.message ?? "Your request was submitted for institutional review.");
      event.currentTarget.reset();
    } else {
      setMessage(typeof data.detail === "string" ? data.detail : "The access request could not be submitted.");
    }
    setBusy(false);
  }

  return (
    <main id="main-content" className="auth-page">
      <section className="auth-card">
        <div className="brand-mark">LS</div>
        <span className="eyebrow">Controlled institutional onboarding</span>
        <h1>Request access</h1>
        <p>
          This form does not create an account or assign a role. An authorised Institution
          Administrator must review the request and send a secure invitation.
        </p>
        <form onSubmit={submit}>
          <label><span>Institution code</span><input name="institution_slug" required /></label>
          <label><span>Institutional email</span><input name="email" type="email" required /></label>
          <label><span>Given name</span><input name="given_name" required /></label>
          <label><span>Family name</span><input name="family_name" required /></label>
          <label><span>Position or title</span><input name="position_title" /></label>
          <label>
            <span>Role requested for review</span>
            <select name="requested_role_code" defaultValue="">
              <option value="">Choose only when known</option>
              <option value="lecturer">Lecturer</option>
              <option value="module_coordinator">Module Coordinator</option>
              <option value="programme_coordinator">Programme Coordinator</option>
              <option value="head_of_department">Head of Department</option>
              <option value="internal_moderator">Internal Moderator</option>
              <option value="external_moderator">External Moderator</option>
              <option value="external_reviewer">External Reviewer</option>
            </select>
          </label>
          <label><span>Reason for access</span><textarea name="request_message" rows={4} /></label>
          {message && <div className={submitted ? "notice" : "error-notice"}>{message}</div>}
          <button className="submit-button" disabled={busy || submitted}>
            {busy ? "Submitting…" : submitted ? "Request submitted" : "Submit request"}
          </button>
          <Link href="/sign-in" className="link-button">Back to sign in</Link>
        </form>
      </section>
    </main>
  );
}
