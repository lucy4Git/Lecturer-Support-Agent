import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { backendUrl, parseBackendResponse } from "@/lib/server-api";
export async function POST(request: Request) {
  const response = await fetch(backendUrl("/api/v1/auth/sso/exchange"), { method: "POST", headers: { "Content-Type": "application/json", "User-Agent": request.headers.get("user-agent") || "LecturerSupportAgentWeb" }, body: await request.text(), cache: "no-store" });
  const data = (await parseBackendResponse(response)) as Record<string, unknown>;
  if (!response.ok) return NextResponse.json(data, { status: response.status });
  const store = await cookies(); const secure = process.env.NODE_ENV === "production";
  store.set("lsa_access", String(data.access_token), { httpOnly: true, secure, sameSite: "strict", path: "/", maxAge: 15 * 60 });
  store.set("lsa_refresh", String(data.refresh_token), { httpOnly: true, secure, sameSite: "strict", path: "/", maxAge: 14 * 24 * 60 * 60 });
  store.set("lsa_role", String(data.role_code), { httpOnly: false, secure, sameSite: "strict", path: "/", maxAge: 14 * 24 * 60 * 60 });
  return NextResponse.json({ signed_in: true, role_code: data.role_code });
}
