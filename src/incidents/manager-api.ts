import type {
  IncidentCreateInput,
  IncidentFilters,
  IncidentRecord,
  IncidentStatus,
  IncidentSummary,
} from "./manager-types";
import { ApiRequestError, fetchJson } from "../utils/api-errors";

const API_BASE = "/api/incidents";
const STORAGE_KEY = "trackflow_token";

export class IncidentApiError extends ApiRequestError {
  constructor(message: string, status?: number, field?: string) {
    super(message, status, field);
    this.name = "IncidentApiError";
  }
}

function authHeaders(): HeadersInit {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem(STORAGE_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  try {
    return await fetchJson<T>(path, {
      ...init,
      cache: "no-store",
      headers: {
        ...authHeaders(),
        ...init.headers,
      },
    });
  } catch (error) {
    if (error instanceof ApiRequestError) {
      if (error.status === 401 && typeof window !== "undefined") {
        localStorage.removeItem(STORAGE_KEY);
        window.location.assign("/login");
      }
      throw new IncidentApiError(error.message, error.status, error.field);
    }
    throw new IncidentApiError("The incident request could not be completed.");
  }
}

export function listIncidents(filters: IncidentFilters = {}): Promise<IncidentRecord[]> {
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
