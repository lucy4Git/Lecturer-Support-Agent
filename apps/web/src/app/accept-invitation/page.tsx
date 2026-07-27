"use client";

import { FormEvent, useState } from "react";
import { useSearchParams } from "next/navigation";

export default function AcceptInvitationPage() {
  const searchParams = useSearchParams();
  const [message, setMessage] = useState<string | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const values = new FormData(event.currentTarget);
    const response = await fetch("/api/session/accept-invitation", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ invitation_token: searchParams.get("token"), given_name: values.get("given_name"), family_name: values.get("family_name"), password: values.get("password") }) });
    const data = await response.json().catch(() => ({}));
    setMessage(response.ok ? data.message : typeof data.detail === "string" ? data.detail : "Invitation could not be accepted.");
  }
  return <main className="auth-page"><section className="auth-card"><div className="brand-mark">LS</div><h1>Accept invitation</h1><form onSubmit={submit}><label><span>Given name</span><input name="given_name" required /></label><label><span>Family name</span><input name="family_name" required /></label><label><span>Create password</span><input name="password" type="password" required /></label>{message && <div className="notice">{message}</div>}<button className="submit-button">Accept invitation</button></form></section></main>;
}
