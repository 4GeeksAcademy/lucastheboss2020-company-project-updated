import { NextRequest, NextResponse } from "next/server";

const backofficeInternalUrl = process.env.BACKOFFICE_INTERNAL_URL;

export async function POST(request: NextRequest) {
  if (!backofficeInternalUrl) {
    return NextResponse.json({ error: "Lead service is not configured. Please retry later." }, { status: 503 });
  }

  try {
    const response = await fetch(`${backofficeInternalUrl}/api/candidates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: await request.text(),
      cache: "no-store",
    });
    const body = await response.text();
    return new NextResponse(body, {
      status: response.status,
      headers: { "Content-Type": response.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json({ error: "Lead service is unavailable. Please retry." }, { status: 503 });
  }
}