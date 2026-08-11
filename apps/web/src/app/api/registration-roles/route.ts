import { NextResponse } from "next/server";
import { backendUrl, parseBackendResponse } from "@/lib/server-api";

export async function GET(): Promise<NextResponse> {
  const response = await fetch(backendUrl("/api/v1/auth/registration-roles"), {
    cache: "no-store",
  });
  const data = await parseBackendResponse(response);
  return NextResponse.json(data, { status: response.status });
}
