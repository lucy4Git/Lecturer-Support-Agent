import { NextResponse } from "next/server";
import { backendUrl, parseBackendResponse } from "@/lib/server-api";

export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams } = new URL(request.url);
  const q = searchParams.get("q") ?? "";
  const url = backendUrl(`/api/v1/auth/institutions?q=${encodeURIComponent(q)}`);
  const response = await fetch(url, { cache: "no-store" });
  const data = await parseBackendResponse(response);
  return NextResponse.json(data, { status: response.status });
}
