import type {
  IncidentCreateInput,
  IncidentFilters,
  IncidentListItem,
  IncidentRecord,
  IncidentStatus,
  IncidentSummary,
} from "./manager-types";
import { ApiRequestError, fetchJson } from "../utils/api-errors";
import { TRACKFLOW_TOKEN_KEY, trackFlowAuthHeaders } from "../utils/auth-headers";

const API_BASE = "/api/incidents";

export class IncidentApiError extends ApiRequestError {
  constructor(message: string, status?: number, field?: string) {
    super(message, status, field);
    this.name = "IncidentApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  try {
    return await fetchJson<T>(path, {
      ...init,
      cache: "no-store",
      headers: {
        ...trackFlowAuthHeaders(),
        ...init.headers,
      },
    });
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.status === 401 && typeof window !== "undefined") {
        localStorage.removeItem(TRACKFLOW_TOKEN_KEY);
        window.location.assign("/login");
      }
      throw new IncidentApiError(error.message, error.status, error.field);
    }
    throw new IncidentApiError("The incident request could not be completed.");
  }
}

export function listIncidents(filters: IncidentFilters = {}): Promise<IncidentListItem[]> {
  const params = new URLSearchParams();
  for (const key of ["status", "origin", "branch", "category"] as const) {
    const value = filters[key];
    if (value) params.set(key, value);
  }
  const query = params.toString();
  return request(`${API_BASE}${query ? `?${query}` : ""}`);
}

export function getIncident(incidentId: string): Promise<IncidentRecord> {
  return request(`${API_BASE}/${encodeURIComponent(incidentId)}`);
}

export function createIncident(payload: IncidentCreateInput): Promise<IncidentRecord> {
  return request(API_BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function changeIncidentStatus(
  incidentId: string,
  nextStatus: IncidentStatus,
): Promise<IncidentRecord> {
  return request(`${API_BASE}/${encodeURIComponent(incidentId)}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: nextStatus }),
  });
}

export function getIncidentSummary(): Promise<IncidentSummary> {
  return request(`${API_BASE}/summary`);
}
