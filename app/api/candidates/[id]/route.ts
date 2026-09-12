import { NextResponse } from "next/server";
import { getCandidate, patchCandidate, replaceCandidate } from "../data";
import type { CandidateWriteInput } from "../../../../src/candidates/types";
import { requireAuthentication } from "../../_auth";

interface RouteContext {
  params: { id: string };
}

export async function GET(_request: Request, { params }: RouteContext) {
  const authError = requireAuthentication(_request);
  if (authError) return authError;
  const candidate = getCandidate(params.id);

  if (!candidate) {
    return NextResponse.json({ error: "Candidate was not found." }, { status: 404 });
  }

  return NextResponse.json(candidate);
}

export async function PATCH(request: Request, { params }: RouteContext) {
  const authError = requireAuthentication(request);
  if (authError) return authError;
  const body = (await request.json()) as { status?: string; stage?: string };
  const result = patchCandidate(params.id, body);

  if (!result.candidate) {
    return NextResponse.json({ error: result.errors?.join(" ") ?? "Candidate could not be updated." }, { status: 400 });
  }

  return NextResponse.json(result.candidate);
}

export async function PUT(request: Request, { params }: RouteContext) {
  const authError = requireAuthentication(request);
  if (authError) return authError;
  const body = (await request.json()) as CandidateWriteInput;
  const result = replaceCandidate(params.id, body);

  if (!result.candidate) {
    return NextResponse.json({ error: result.errors?.join(" ") ?? "Candidate could not be saved." }, { status: 400 });
  }

  return NextResponse.json(result.candidate);
}
