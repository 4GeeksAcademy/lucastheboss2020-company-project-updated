import type { CandidateWriteInput } from "../../../src/candidates/types";
import { NextResponse } from "next/server";

const REQUIRED_STRING_FIELDS = [
  "companyName",
  "contactPerson",
  "corporateEmail",
  "phone",
  "operatingCountry",
  "productType",
  "monthlyVolume",
  "current3pl",
  "status",
  "stage",
  "assignedTo",
] as const;

export function isCandidateWriteInput(value: unknown): value is CandidateWriteInput {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const input = value as Record<string, unknown>;
  if (!REQUIRED_STRING_FIELDS.every((field) => typeof input[field] === "string")) return false;
  if (!Array.isArray(input.servicesOfInterest) || !input.servicesOfInterest.every((item) => typeof item === "string")) return false;
  if (typeof input.privacyAccepted !== "boolean") return false;
  if (input.companyWebsite !== undefined && typeof input.companyWebsite !== "string") return false;
  if (input.comments !== undefined && typeof input.comments !== "string") return false;
  return true;
}

export function isCandidateProgressPatch(value: unknown): value is { status?: string; stage?: string } {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const patch = value as Record<string, unknown>;
  const statusValid = patch.status === undefined || typeof patch.status === "string";
  const stageValid = patch.stage === undefined || typeof patch.stage === "string";
  return statusValid && stageValid && (patch.status !== undefined || patch.stage !== undefined);
}

export function candidateMutationError(errors: string[] | undefined, fallback: string): NextResponse {
  const message = errors?.join(" ") ?? fallback;
  const status = /not found/i.test(message) ? 404 : 400;
  return NextResponse.json({ error: message }, { status });
}
