"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import PasswordInput from "@/components/PasswordInput";

type Institution = {
  id: string;
  display_name: string;
  institution_type: string;
};

type RoleOption = {
  role_code: string;
  role_name: string;
};

export default function SignUpPage() {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);
  const [busy, setBusy] = useState(false);

  const [roles, setRoles] = useState<RoleOption[]>([]);
  const [rolesLoading, setRolesLoading] = useState(true);

  const [institutionQuery, setInstitutionQuery] = useState("");
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [selectedInstitution, setSelectedInstitution] = useState<Institution | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch permitted roles from the authoritative backend catalogue on mount.
  useEffect(() => {
    fetch("/api/registration-roles")
      .then((r) => r.ok ? r.json() : [])
      .then((data: RoleOption[]) => setRoles(data))
      .catch(() => setRoles([]))
      .finally(() => setRolesLoading(false));
  }, []);

  const searchInstitutions = useCallback(async (q: string) => {
    if (!q.trim()) { setInstitutions([]); return; }
    try {
      const res = await fetch(`/api/institutions?q=${encodeURIComponent(q)}`);
      if (res.ok) setInstitutions(await res.json());
    } catch {}
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => searchInstitutions(institutionQuery), 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [institutionQuery, searchInstitutions]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedInstitution) {
      setIsError(true);
      setMessage("Please select your institution from the list.");
      return;
    }
    setBusy(true);
    setMessage(null);
    setIsError(false);
    const values = new FormData(event.currentTarget);

    const response = await fetch("/api/session/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        institution_id: selectedInstitution.id,
        email: values.get("email"),
        password: values.get("password"),
        role_code: values.get("role_code"),
      }),
    });

    const data = await response.json().catch(() => ({}));
    if (response.ok) {
      router.replace("/");
      router.refresh();
      return;
    }

    setIsError(true);
    const detail = data.detail;
    setMessage(typeof detail === "string" ? detail : detail?.message ?? "Account creation failed.");
    setBusy(false);
  }

  return (
    <main id="main-content" className="auth-page">
      <section className="auth-card">
        <div className="brand-mark">LS</div>
        <span className="eyebrow">Lecturer Support Agent</span>
        <h1>Create an account</h1>
        <p>Select your institution, enter your email address and password, and choose your role.</p>
        <form onSubmit={submit}>

          <div ref={searchRef} style={{ position: "relative" }}>
            <label>
              <span>Institution / University</span>
              <input
                type="text"
                placeholder="Type to search…"
                autoComplete="off"
                value={selectedInstitution ? selectedInstitution.display_name : institutionQuery}
                onChange={(e) => {
                  setSelectedInstitution(null);
                  setInstitutionQuery(e.target.value);
                  setShowDropdown(true);
                }}
                onFocus={() => { if (institutions.length) setShowDropdown(true); }}
                required={!selectedInstitution}
              />
            </label>
            {showDropdown && institutions.length > 0 && !selectedInstitution && (
              <ul className="autocomplete-list" role="listbox">
                {institutions.map((inst) => (
                  <li
                    key={inst.id}
                    role="option"
                    aria-selected={false}
                    className="autocomplete-item"
                    onMouseDown={() => {
                      setSelectedInstitution(inst);
                      setInstitutionQuery(inst.display_name);
                      setShowDropdown(false);
                    }}
                  >
                    <span className="autocomplete-name">{inst.display_name}</span>
                    <span className="autocomplete-type">{inst.institution_type.replace(/_/g, " ")}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <label>
            <span>Institution email</span>
            <input name="email" type="email" autoComplete="email" required />
          </label>

          <label>
            <span>Password</span>
            <PasswordInput name="password" autoComplete="new-password" required />
          </label>
          <p className="password-hint">
            At least 12 characters including uppercase, lowercase, number and symbol.
          </p>

          <label>
            <span>Role</span>
            <select name="role_code" required defaultValue="" disabled={rolesLoading}>
              <option value="" disabled>
                {rolesLoading ? "Loading roles…" : "Select your role"}
              </option>
              {roles.map((r) => (
                <option key={r.role_code} value={r.role_code}>{r.role_name}</option>
              ))}
            </select>
          </label>

          {message && (
            <div className={isError ? "error-notice" : "notice"}>{message}</div>
          )}

          <button className="submit-button" disabled={busy || rolesLoading}>
            {busy ? "Creating account…" : "Create account"}
          </button>
          <Link href="/sign-in" className="link-button">Already have an account? Sign in</Link>
        </form>
      </section>
    </main>
  );
}
