import { NextResponse } from "next/server";
import { backendUrl } from "@/lib/server-api";

// Short-lived warm-up route.  A GET to this endpoint wakes both the Railway
// API process and the Neon serverless database before the caller issues any
// state-changing request.  Safe to call without side effects.
export const maxDuration = 60;

export async function GET(): Promise<NextResponse> {
  try {
    await fetch(backendUrl("/api/v1/auth/institutions?q=ping"), {
      cache: "no-store",
      signal: AbortSignal.timeout(55_000),
    });
  } catch {
    // Warm-up failure is non-fatal — the caller will proceed anyway.
  }
  return new NextResponse(null, { status: 204 });
}
