import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { backendUrl, parseBackendResponse } from "@/lib/server-api";

export async function POST(request: Request): Promise<NextResponse> {
  const response = await fetch(backendUrl("/api/v1/auth/login"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
    cache: "no-store",
  });
  const data = (await parseBackendResponse(response)) as Record<string, unknown>;
  if (!response.ok) return NextResponse.json(data, { status: response.status });

  const cookieStore = await cookies();
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
  cookieStore.set("lsa_role", String(data.role_code), {
    httpOnly: false,
    secure,
    sameSite: "strict",
    path: "/",
    maxAge: 14 * 24 * 60 * 60,
  });
  return NextResponse.json({
    tenant_id: data.tenant_id,
    user_id: data.user_id,
    role_code: data.role_code,
  });
}
