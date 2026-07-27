import { NextResponse } from "next/server";
import { backendUrl, parseBackendResponse } from "@/lib/server-api";

export async function POST(request: Request): Promise<NextResponse> {
  const response = await fetch(backendUrl("/api/v1/auth/invitations/accept"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
    cache: "no-store",
  });
  const data = await parseBackendResponse(response);
  return NextResponse.json(data, { status: response.status });
}
