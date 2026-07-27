import { NextResponse } from "next/server";
import { backendUrl, parseBackendResponse } from "@/lib/server-api";
export async function POST(request: Request) {
  const response = await fetch(backendUrl("/api/v1/auth/password-reset/confirm"), { method: "POST", headers: { "Content-Type": "application/json" }, body: await request.text(), cache: "no-store" });
  const data = response.status === 204 ? { reset: true } : await parseBackendResponse(response);
  return NextResponse.json(data, { status: response.status === 204 ? 200 : response.status });
}
