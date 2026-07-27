import { NextResponse } from "next/server";
import { backendUrl, parseBackendResponse } from "@/lib/server-api";
export async function POST(request: Request) {
  const response = await fetch(backendUrl("/api/v1/auth/password-reset/request"), { method: "POST", headers: { "Content-Type": "application/json" }, body: await request.text(), cache: "no-store" });
  return NextResponse.json(await parseBackendResponse(response), { status: response.status });
}
