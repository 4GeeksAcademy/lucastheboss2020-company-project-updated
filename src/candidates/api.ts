import type { Candidate, CandidateListResponse, CandidateWriteInput } from "./types";
import { authenticatedFetch, readJson } from "../auth";

async function parseResponse<T>(response: Response): Promise<T> {
  return readJson<T>(response);
}

export async function fetchCandidates(search: string): Promise<CandidateListResponse> {
  const response = await authenticatedFetch(`/api/candidates${search}`, { cache: "no-store" });
  return parseResponse<CandidateListResponse>(response);
}

export async function fetchCandidate(id: string): Promise<Candidate> {
  const response = await authenticatedFetch(`/api/candidates/${id}`, { cache: "no-store" });
  return parseResponse<Candidate>(response);
}

export async function createCandidate(input: CandidateWriteInput): Promise<Candidate> {
  const response = await authenticatedFetch("/api/candidates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseResponse<Candidate>(response);
}

export async function updateCandidate(id: string, input: CandidateWriteInput): Promise<Candidate> {
  const response = await authenticatedFetch(`/api/candidates/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseResponse<Candidate>(response);
}

export async function patchCandidateProgress(id: string, status: Candidate["status"], stage: Candidate["stage"]): Promise<Candidate> {
  const response = await authenticatedFetch(`/api/candidates/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, stage }),
  });
  return parseResponse<Candidate>(response);
}

export async function addCandidateNote(id: string, body: string): Promise<Candidate> {
  const response = await authenticatedFetch(`/api/candidates/${id}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body }),
  });
  return parseResponse<Candidate>(response);
}

export async function deleteCandidateNote(id: string, noteId: string): Promise<Candidate> {
  const response = await authenticatedFetch(`/api/candidates/${id}/notes/${noteId}`, { method: "DELETE" });
  return parseResponse<Candidate>(response);
}
