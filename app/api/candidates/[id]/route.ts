import { NextRequest, NextResponse } from "next/server";
import { getCandidate, patchCandidate, replaceCandidate } from "../data";
import type { CandidateWriteInput } from "../../../../src/candidates/types";
import { requireAuthentication } from "../../_auth";
import { internalServerError, readJsonObject } from "../../_request";
import { candidateMutationError, isCandidateProgressPatch, isCandidateWriteInput } from "../validation";

interface RouteContext {
  params: { id: string };
}

export async function GET(request: NextRequest, { params }: RouteContext) {
  const authError = requireAuthentication(request);
  if (authError) return authError;

  let candidate;
  try {
    candidate = getCandidate(params.id);
  } catch {
    return internalServerError("Candidate details could not be loaded. Please retry.");
  }

  if (!candidate) {
    return NextResponse.json({ error: "Candidate was not found." }, { status: 404 });
  }

  return NextResponse.json(candidate);
}

export async function PATCH(request: NextRequest, { params }: RouteContext) {
  const authError = requireAuthentication(request);
  if (authError) return authError;

  const parsed = await readJsonObject(request);
  if (!parsed.ok) return parsed.response;
  if (!isCandidateProgressPatch(parsed.value)) {
    return NextResponse.json({ error: "Provide a valid candidate status or stage." }, { status: 400 });
  }

  let result;
  try {
    result = patchCandidate(params.id, parsed.value);
  } catch {
    return internalServerError("Candidate progress could not be updated. Please retry.");
  }

  if (!result.candidate) {
    return candidateMutationError(result.errors, "Candidate could not be updated.");
  }

  return NextResponse.json(result.candidate);
}

export async function PUT(request: NextRequest, { params }: RouteContext) {
  const authError = requireAuthentication(request);
  if (authError) return authError;

  const parsed = await readJsonObject(request);
  if (!parsed.ok) return parsed.response;
  if (!isCandidateWriteInput(parsed.value)) {
    return NextResponse.json({ error: "Candidate information is incomplete or malformed." }, { status: 400 });
  }

  let result;
  try {
    result = replaceCandidate(params.id, parsed.value as CandidateWriteInput);
  } catch {
    return internalServerError("Candidate could not be updated. Please retry.");
  }

  if (!result.candidate) {
    return candidateMutationError(result.errors, "Candidate could not be saved.");
  }

  return NextResponse.json(result.candidate);
}
