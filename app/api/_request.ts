import { NextResponse } from "next/server";

export type JsonObjectResult =
  | { ok: true; value: Record<string, unknown> }
  | { ok: false; response: NextResponse };

export async function readJsonObject(request: Request): Promise<JsonObjectResult> {
  let value: unknown;
  try {
    value = await request.json();
  } catch {
    return {
      ok: false,
      response: NextResponse.json({ error: "Request body must contain valid JSON." }, { status: 400 }),
    };
  }

  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return {
      ok: false,
      response: NextResponse.json({ error: "Request body must be a JSON object." }, { status: 400 }),
    };
  }

  return { ok: true, value: value as Record<string, unknown> };
}

export function internalServerError(message = "The request could not be completed. Please try again."): NextResponse {
  return NextResponse.json({ error: message }, { status: 500 });
}
