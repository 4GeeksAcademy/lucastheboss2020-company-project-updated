import { NextResponse } from "next/server";
import { createCandidate, listCandidates } from "./data";
import type { CandidateWriteInput } from "../../../src/candidates/types";
import { requireAuthentication } from "../_auth";

export async function GET(request: Request) {
  const authError = requireAuthentication(request);
  if (authError) return authError;
  const url = new URL(request.url);
  return NextResponse.json(listCandidates(url.searchParams));
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as CandidateWriteInput;
    const result = createCandidate(body);

    if (!result.candidate) {
      return NextResponse.json({ error: result.errors?.join(" ") ?? "Candidate could not be created." }, { status: 400 });
    }

    return NextResponse.json(result.candidate, { status: 201 });
  } catch {
    return NextResponse.json({ error: "Candidate request payload is invalid." }, { status: 400 });
  }
}
