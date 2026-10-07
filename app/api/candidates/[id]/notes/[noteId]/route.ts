import { NextRequest, NextResponse } from "next/server";
import { deleteNote } from "../../../data";
import { requireAuthentication } from "../../../../_auth";
import { internalServerError } from "../../../../_request";
import { candidateMutationError } from "../../../validation";

interface RouteContext {
  params: { id: string; noteId: string };
}

export async function DELETE(request: NextRequest, { params }: RouteContext) {
  const authError = requireAuthentication(request);
  if (authError) return authError;

  let result;
  try {
    result = deleteNote(params.id, params.noteId);
  } catch {
    return internalServerError("The note could not be deleted. Please retry.");
  }

  if (!result.candidate) {
    return candidateMutationError(result.errors, "Note could not be deleted.");
  }

  return NextResponse.json(result.candidate);
}
