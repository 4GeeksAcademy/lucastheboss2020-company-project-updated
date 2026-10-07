import { NextRequest, NextResponse } from "next/server";
import { createCandidate, listCandidates } from "./data";
import type { CandidateWriteInput } from "../../../src/candidates/types";
import { hasValidBearerToken, unauthorized } from "../_auth";
import { internalServerError, readJsonObject } from "../_request";
import { isCandidateWriteInput } from "./validation";

export async function GET(request: NextRequest) {
  if (!hasValidBearerToken(request)) {
    return unauthorized();
  }
  try {
    const url = new URL(request.url);
    return NextResponse.json(listCandidates(url.searchParams));
  } catch {
    return internalServerError("Candidates could not be loaded. Please retry.");
  }
}

export async function POST(request: NextRequest) {
  // Lead capture is public — no auth required
  const parsed = await readJsonObject(request);
  if (!parsed.ok) return parsed.response;
  if (!isCandidateWriteInput(parsed.value)) {
    return NextResponse.json({ error: "Candidate information is incomplete or malformed." }, { status: 400 });
  }

  try {
    const result = createCandidate(parsed.value as CandidateWriteInput);
    if (!result.candidate) {
      return NextResponse.json({ error: result.errors?.join(" ") ?? "Candidate could not be created." }, { status: 400 });
    }

    return NextResponse.json(result.candidate, { status: 201 });
  } catch {
    return internalServerError("Candidate request could not be processed. Please retry.");
  }
}
