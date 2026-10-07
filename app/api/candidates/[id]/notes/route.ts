import { NextRequest, NextResponse } from "next/server";
import { addNote } from "../../data";
import { requireAuthentication } from "../../../_auth";
import { internalServerError, readJsonObject } from "../../../_request";
import { candidateMutationError } from "../../validation";

interface RouteContext {
  params: { id: string };
}

export async function POST(request: NextRequest, { params }: RouteContext) {
  const authError = requireAuthentication(request);
  if (authError) return authError;

  const parsed = await readJsonObject(request);
  if (!parsed.ok) return parsed.response;
  if (parsed.value.body !== undefined && typeof parsed.value.body !== "string") {
    return NextResponse.json({ error: "Note text must be a string." }, { status: 400 });
  }

  let result;
  try {
    result = addNote(params.id, (parsed.value.body as string | undefined) ?? "");
  } catch {
    return internalServerError("The note could not be added. Please retry.");
  }

  if (!result.candidate) {
    return candidateMutationError(result.errors, "Note could not be added.");
  }

  return NextResponse.json(result.candidate, { status: 201 });
}
