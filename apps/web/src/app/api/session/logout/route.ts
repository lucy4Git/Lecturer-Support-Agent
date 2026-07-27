import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { backendUrl } from "@/lib/server-api";

export async function POST(): Promise<NextResponse> {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get("lsa_refresh")?.value;
  if (refreshToken) {
    await fetch(backendUrl("/api/v1/auth/logout"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken, all_sessions: false }),
      cache: "no-store",
    }).catch(() => undefined);
  }
  for (const name of ["lsa_access", "lsa_refresh", "lsa_role"]) cookieStore.delete(name);
  return NextResponse.json({ signed_out: true });
}
