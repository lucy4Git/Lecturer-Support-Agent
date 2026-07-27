import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { backendUrl, parseBackendResponse } from "@/lib/server-api";

export async function POST(): Promise<NextResponse> {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get("lsa_refresh")?.value;
  if (!refreshToken) return NextResponse.json({ detail: "No refresh session." }, { status: 401 });
  const response = await fetch(backendUrl("/api/v1/auth/refresh"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: "no-store",
  });
  const data = (await parseBackendResponse(response)) as Record<string, unknown>;
  if (!response.ok) return NextResponse.json(data, { status: response.status });
  const secure = process.env.NODE_ENV === "production";
  cookieStore.set("lsa_access", String(data.access_token), {
    httpOnly: true,
    secure,
    sameSite: "strict",
    path: "/",
    maxAge: 15 * 60,
  });
  cookieStore.set("lsa_refresh", String(data.refresh_token), {
    httpOnly: true,
    secure,
    sameSite: "strict",
    path: "/",
    maxAge: 14 * 24 * 60 * 60,
  });
  return NextResponse.json({ refreshed: true });
}
