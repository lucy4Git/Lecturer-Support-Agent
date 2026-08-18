import { NextResponse } from "next/server";
import { backendUrl, parseBackendResponse } from "@/lib/server-api";

// Allow up to 60 s so Railway's cold-start (typically 15-25 s) is absorbed.
// Vercel Hobby caps this at 10 s; Vercel Pro honours it up to 300 s.
export const maxDuration = 60;

export async function POST(request: Request): Promise<NextResponse> {
  const body = await request.text();

  // Pre-warm Railway before the state-changing POST.
  // If the API process is sleeping, this GET absorbs the cold-start delay so
  // the subsequent reset POST completes quickly. The warm-up uses a read-only
  // endpoint; failure is silently ignored — we still attempt the reset.
  try {
    await fetch(backendUrl("/api/v1/auth/institutions?q=ping"), {
      cache: "no-store",
      signal: AbortSignal.timeout(50_000),
    });
  } catch {
    // Warm-up timed out or failed — proceed anyway.
  }

  let response: Response;
  try {
    response = await fetch(backendUrl("/api/v1/auth/direct-reset"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(12_000),
    });
  } catch (err) {
    const isTimeout = err instanceof Error && err.name === "TimeoutError";
    return NextResponse.json(
      {
        detail: isTimeout
          ? "The service is taking longer than expected. Please wait a moment and try again."
          : "The request could not be completed. Please try again.",
      },
      { status: 503 },
    );
  }

  if (response.status === 204) return new NextResponse(null, { status: 204 });
  const data = await parseBackendResponse(response);
  return NextResponse.json(data, { status: response.status });
}
