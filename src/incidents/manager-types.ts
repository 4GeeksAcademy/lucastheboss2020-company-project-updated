export const INCIDENT_CATEGORIES = [
  "lost_parcel",
  "delivery_failure",
  "inventory_discrepancy",
  "carrier_issue",
  "returns_issue",
  "warehouse_incident",
  "system_failure",
  "client_complaint",
  "other",
] as const;

export const INCIDENT_STATUSES = ["open", "in_progress", "resolved", "discarded"] as const;
export const INCIDENT_ORIGINS = ["customer", "branch", "internal"] as const;
export const INCIDENT_BRANCHES = [
  "central",
  "la_warehouse",
  "la_office",
  "zaragoza_warehouse",
  "zaragoza_office",
] as const;

export type IncidentCategory = (typeof INCIDENT_CATEGORIES)[number];
export type IncidentStatus = (typeof INCIDENT_STATUSES)[number];
export type IncidentOrigin = (typeof INCIDENT_ORIGINS)[number];
export type IncidentBranch = (typeof INCIDENT_BRANCHES)[number];

export interface IncidentRecord {
  id: string;
  title: string;
  description: string;
  category: IncidentCategory;
  status: IncidentStatus;
  origin: IncidentOrigin;
  branch: IncidentBranch;
  created_at: string;
  updated_at: string;
}

export interface IncidentCreateInput {
  title: string;
  description: string;
  category: IncidentCategory;
  origin: IncidentOrigin;
  branch: IncidentBranch;
}

export interface IncidentFilters {
  status?: IncidentStatus | "";
  origin?: IncidentOrigin | "";
  branch?: IncidentBranch | "";
  category?: IncidentCategory | "";
}

export interface IncidentSummary {
  total: number;
  by_status: Record<IncidentStatus, number>;
  by_category: Record<IncidentCategory, number>;
  by_origin: Record<IncidentOrigin, number>;
  by_branch: Record<IncidentBranch, number>;
  critical_open_by_branch: Record<IncidentBranch, number>;
  unresolved_over_24_hours: {
    count: number;
    incidents: IncidentRecord[];
  };
}
