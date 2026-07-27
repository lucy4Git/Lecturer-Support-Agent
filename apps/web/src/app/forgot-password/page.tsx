"use client";
import Link from "next/link";
import { FormEvent, useState } from "react";
export default function ForgotPasswordPage() {
  const [message, setMessage] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setBusy(true); const values = new FormData(event.currentTarget); const response = await fetch("/api/session/password-reset/request", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ institution_slug: values.get("institution_slug"), email: values.get("email") }) }); const data = await response.json().catch(() => ({})); setMessage(data.message || (response.ok ? "Check your email for reset instructions." : "The request could not be processed.")); setBusy(false); }
  return <main className="auth-page"><section className="auth-card"><div className="brand-mark">LS</div><span className="eyebrow">Account recovery</span><h1>Reset your password</h1><p>Enter your institution and email. The response is the same whether or not an eligible account exists.</p><form onSubmit={submit}><label><span>Institution code</span><input name="institution_slug" required /></label><label><span>Email</span><input type="email" name="email" required /></label>{message && <div className="notice">{message}</div>}<button className="submit-button" disabled={busy}>{busy ? "Submitting…" : "Send reset instructions"}</button></form><Link href="/sign-in" className="link-button">Return to sign in</Link></section></main>;
}
