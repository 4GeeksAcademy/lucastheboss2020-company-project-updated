import type { Candidate, CandidateListResponse, CandidateWriteInput } from "./types";

function authHeaders(): HeadersInit {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("trackflow_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = await response.json();

  if (response.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("trackflow_token");
      window.location.href = "/login";
    }
    throw new Error("Session expired. Please log in again.");
  }

  if (!response.ok) {
    throw new Error(payload.error ?? "The TrackFlow candidate request failed.");
  }

  return payload as T;
}

export async function fetchCandidates(search: string): Promise<CandidateListResponse> {
  const response = await fetch(`/api/candidates${search}`, { cache: "no-store", headers: { ...authHeaders() } });
  return parseResponse<CandidateListResponse>(response);
}

export async function fetchCandidate(id: string): Promise<Candidate> {
  const response = await fetch(`/api/candidates/${id}`, { cache: "no-store", headers: { ...authHeaders() } });
  return parseResponse<Candidate>(response);
}

export async function createCandidate(input: CandidateWriteInput): Promise<Candidate> {
  const response = await fetch("/api/candidates", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(input),
  });
  return parseResponse<Candidate>(response);
}

export async function updateCandidate(id: string, input: CandidateWriteInput): Promise<Candidate> {
  const response = await fetch(`/api/candidates/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(input),
  });
  return parseResponse<Candidate>(response);
}

export async function patchCandidateProgress(id: string, status: Candidate["status"], stage: Candidate["stage"]): Promise<Candidate> {
  const response = await fetch(`/api/candidates/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ status, stage }),
  });
  return parseResponse<Candidate>(response);
}

export async function addCandidateNote(id: string, body: string): Promise<Candidate> {
  const response = await fetch(`/api/candidates/${id}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ body }),
  });
  return parseResponse<Candidate>(response);
}

export async function deleteCandidateNote(id: string, noteId: string): Promise<Candidate> {
  const response = await fetch(`/api/candidates/${id}/notes/${noteId}`, { method: "DELETE", headers: { ...authHeaders() } });
  return parseResponse<Candidate>(response);
}
