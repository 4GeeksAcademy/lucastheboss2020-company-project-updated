import type { NextRequest } from "next/server";

const INCIDENTS_SERVICE_URL = process.env.INCIDENTS_SERVICE_URL ?? "http://localhost:8002";

export async function proxyManagerRequest(
  request: NextRequest,
  servicePath: string,
): Promise<Response> {
  const headers = new Headers({ Accept: "application/json" });
  const authorization = request.headers.get("authorization");
  if (authorization) headers.set("Authorization", authorization);

  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);

  let body: string | undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    body = await request.text();
  }

  try {
    const upstream = await fetch(`${INCIDENTS_SERVICE_URL}${servicePath}`, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
    });
    const responseBody = await upstream.text();

    return new Response(responseBody, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return Response.json(
      { error: { message: "The incident service is unavailable. Please try again." } },
      { status: 503 },
    );
  }
}
