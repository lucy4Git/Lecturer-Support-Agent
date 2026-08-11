import { NextResponse } from "next/server";
import { backendUrl, parseBackendResponse } from "@/lib/server-api";

export async function POST(request: Request): Promise<NextResponse> {
  const response = await fetch(backendUrl("/api/v1/auth/direct-reset"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
    cache: "no-store",
  });
  if (response.status === 204) return new NextResponse(null, { status: 204 });
  const data = await parseBackendResponse(response);
  return NextResponse.json(data, { status: response.status });
}
