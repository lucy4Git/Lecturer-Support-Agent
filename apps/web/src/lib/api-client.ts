"use client";

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const execute = () => {
    const headers = new Headers(init.headers ?? {});
    if (!(init.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    return fetch(`/api/backend/${path.replace(/^\//, "")}`, { ...init, headers });
  };
  let response = await execute();
  if (response.status === 401) {
    const refreshed = await fetch("/api/session/refresh", { method: "POST" });
    if (refreshed.ok) response = await execute();
  }
  return response;
}

export async function responseMessage(response: Response): Promise<string> {
  const data = (await response.json().catch(() => null)) as
    | { detail?: string | { message?: string } }
    | null;
  if (typeof data?.detail === "string") return data.detail;
  if (data?.detail && typeof data.detail === "object" && data.detail.message) return data.detail.message;
  return response.ok ? "Completed." : "The request could not be completed.";
}
