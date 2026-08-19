import { NextResponse } from "next/server";
import { backendUrl, parseBackendResponse } from "@/lib/server-api";

// 60 s on Pro; Hobby caps at 10 s.  Railway + Neon should already be warm
// because the client calls /api/session/ping first — so this is fast.
export const maxDuration = 60;

export async function POST(request: Request): Promise<NextResponse> {
  const body = await request.text();

  let response: Response;
  try {
    response = await fetch(backendUrl("/api/v1/auth/direct-reset"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(55_000),
    });
  } catch (err) {
    const isTimeout = err instanceof Error && err.name === "TimeoutError";
    return NextResponse.json(
      {
        detail: isTimeout
          ? "The service is warming up. Please wait a moment and try again."
          : "The request could not be completed. Please try again.",
      },
      { status: 503 },
    );
  }

  if (response.status === 204) return new NextResponse(null, { status: 204 });
  const data = await parseBackendResponse(response);
  return NextResponse.json(data, { status: response.status });
}
