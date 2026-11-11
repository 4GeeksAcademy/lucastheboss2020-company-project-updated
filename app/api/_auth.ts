import type { NextRequest } from "next/server";

const API_INTERNAL_URL = (process.env.API_INTERNAL_URL ?? "http://localhost:8000").replace(/\/+$/, "");

export function unauthorized(): Response {
  return Response.json({ error: "Unauthorized" }, { status: 401 });
}

export async function requireAuthentication(request: NextRequest): Promise<Response | undefined> {
  const authorization = request.headers.get("authorization");
  if (!authorization?.startsWith("Bearer ")) return unauthorized();

  try {
    const response = await fetch(`${API_INTERNAL_URL}/auth/me`, {
      headers: { Authorization: authorization },
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
    if (response.status === 401 || response.status === 403) return unauthorized();
    if (!response.ok) {
      return Response.json({ error: "Authentication service is unavailable." }, { status: 503 });
    }
    return undefined;
  } catch {
    return Response.json({ error: "Authentication service is unavailable." }, { status: 503 });
  }
}