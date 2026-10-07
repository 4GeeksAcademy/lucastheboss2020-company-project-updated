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

  try {
    let body: string | undefined;
    if (request.method !== "GET" && request.method !== "HEAD") {
      try {
        body = await request.text();
      } catch {
        return Response.json(
          { error: { field: "body", message: "Request body could not be read. Please retry." } },
          { status: 400 },
        );
      }
    }

    const upstream = await fetch(`${INCIDENTS_SERVICE_URL}${servicePath}`, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    const responseBody = await upstream.text();

    return new Response(responseBody, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("content-type") ?? "application/json",
      },
    });
  } catch (error) {
    const timedOut = error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError");
    return Response.json(
      {
        error: {
          message: timedOut
            ? "The incident service took too long to respond. Please retry."
            : "The incident service is unavailable. Please try again.",
        },
      },
      { status: timedOut ? 504 : 503 },
    );
  }
}
