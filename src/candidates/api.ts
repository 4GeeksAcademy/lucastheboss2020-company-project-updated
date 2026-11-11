import type { Candidate, CandidateListResponse, CandidateWriteInput } from "./types";
import { ApiRequestError, fetchJson } from "../utils/api-errors";
import { TRACKFLOW_TOKEN_KEY, trackFlowAuthHeaders } from "../utils/auth-headers";

async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  try {
    return await fetchJson<T>(url, init);
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem(TRACKFLOW_TOKEN_KEY);
      window.location.assign("/login");
    }
    throw error;
  }
}

export async function fetchCandidates(search: string): Promise<CandidateListResponse> {
  return request(`/api/candidates${search}`, { cache: "no-store", headers: { ...trackFlowAuthHeaders() } });
}

export async function fetchCandidate(id: string): Promise<Candidate> {
  return request(`/api/candidates/${encodeURIComponent(id)}`, { cache: "no-store", headers: { ...trackFlowAuthHeaders() } });
}

export async function createCandidate(input: CandidateWriteInput): Promise<Candidate> {
  return request("/api/candidates", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...trackFlowAuthHeaders() },
    body: JSON.stringify(input),
  });
}

export async function updateCandidate(id: string, input: CandidateWriteInput): Promise<Candidate> {
  return request(`/api/candidates/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...trackFlowAuthHeaders() },
    body: JSON.stringify(input),
  });
}

export async function patchCandidateProgress(id: string, status: Candidate["status"], stage: Candidate["stage"]): Promise<Candidate> {
  return request(`/api/candidates/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...trackFlowAuthHeaders() },
    body: JSON.stringify({ status, stage }),
  });
}

export async function addCandidateNote(id: string, body: string): Promise<Candidate> {
  return request(`/api/candidates/${encodeURIComponent(id)}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...trackFlowAuthHeaders() },
    body: JSON.stringify({ body }),
  });
}

export async function deleteCandidateNote(id: string, noteId: string): Promise<Candidate> {
  return request(`/api/candidates/${encodeURIComponent(id)}/notes/${encodeURIComponent(noteId)}`, {
    method: "DELETE",
    headers: { ...trackFlowAuthHeaders() },
  });
}
