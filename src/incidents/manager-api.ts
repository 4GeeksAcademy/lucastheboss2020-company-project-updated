import type {
  IncidentCreateInput,
  IncidentFilters,
  IncidentRecord,
  IncidentStatus,
  IncidentSummary,
} from "./manager-types";

const API_BASE = "/api/incidents";
const STORAGE_KEY = "trackflow_token";

export class IncidentApiError extends Error {
  field?: string;
  status?: number;

  constructor(message: string, status?: number, field?: string) {
    super(message);
    this.name = "IncidentApiError";
    this.status = status;
    this.field = field;
  }
}

function authHeaders(): HeadersInit {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem(STORAGE_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    cache: "no-store",
    headers: {
      ...authHeaders(),
      ...init.headers,
    },
  });

  const payload = await response.json().catch(() => ({}));
  if (response.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem(STORAGE_KEY);
      window.location.assign("/login");
    }
    throw new IncidentApiError("Your session expired. Please sign in again.", 401);
  }

  if (!response.ok) {
    const error = (payload as { error?: { field?: string; message?: string } }).error;
    throw new IncidentApiError(
      error?.message ?? "The incident request could not be completed.",
      response.status,
      error?.field,
    );
  }

  return payload as T;
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
