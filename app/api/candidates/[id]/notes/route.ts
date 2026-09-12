import { NextResponse } from "next/server";
import { addNote } from "../../data";
import { requireAuthentication } from "../../../_auth";

interface RouteContext {
  params: { id: string };
}

export async function POST(request: Request, { params }: RouteContext) {
  const authError = requireAuthentication(request);
  if (authError) return authError;
  const body = (await request.json()) as { body?: string };
  const result = addNote(params.id, body.body ?? "");

  if (!result.candidate) {
    return NextResponse.json({ error: result.errors?.join(" ") ?? "Note could not be added." }, { status: 400 });
  }

  return NextResponse.json(result.candidate, { status: 201 });
}
