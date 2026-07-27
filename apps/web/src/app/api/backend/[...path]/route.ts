import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { backendUrl, parseBackendResponse } from "@/lib/server-api";

async function proxy(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const accessToken = (await cookies()).get("lsa_access")?.value;
  if (!accessToken) return NextResponse.json({ detail: "Authentication required." }, { status: 401 });
  const incomingUrl = new URL(request.url);
  const target = new URL(backendUrl(`/api/v1/${path.join("/")}`));
  target.search = incomingUrl.search;
  const contentType = request.headers.get("content-type");
  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer();
  const headers: Record<string, string> = {
    Authorization: `Bearer ${accessToken}`,
    "X-Request-ID": request.headers.get("x-request-id") ?? crypto.randomUUID(),
  };
  if (contentType) headers["Content-Type"] = contentType;
  const response = await fetch(target, { method: request.method, headers, body, cache: "no-store" });
  const data = await parseBackendResponse(response);
  return NextResponse.json(data, { status: response.status });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
