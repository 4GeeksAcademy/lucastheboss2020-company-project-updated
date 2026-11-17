export interface RfpMetadata {
  client_name: string | null;
  client_country: string | null;
  currency: string | null;
  services_requested: string[];
  monthly_volume: string | null;
  deadline: string | null;
  budget_range: string | null;
  departments_needed: string[];
  evidence: Record<string, string[]>;
  readability_metrics: Record<string, unknown>;
}
export interface RfpSection {
  department_id: "warehouse" | "lastmile" | "reverse";
  owner: string;
  key_aspects: { requirement: string; evidence: string }[];
  open_questions: string[];
}
export interface RfpTicket {
  ticket_id: string;
  rfp_id: string;
  original_filename: string;
  status: string;
  processing_state: string;
  stage: string;
  created_at: string;
  updated_at: string;
  attempts: number;
  error_code: string | null;
  error_message: string | null;
  classification_reason: string | null;
  stalled: boolean;
  can_retry: boolean;
  metadata: RfpMetadata | null;
  sections: RfpSection[];
  handoff: {
    schema_version: number;
    summary: string;
    open_questions: string[];
    conflicts: string[];
    ready_for_part2: boolean;
  } | null;
}
