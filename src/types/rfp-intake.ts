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
  proposal?: ProposalRun | null;
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

export interface ProposalEvaluation {
  department_id: string;
  draft_version: number;
  overall_pass: boolean;
  feedback_for_generator: string;
  readability: {
    pass: boolean;
    score: number | null;
    details: string;
    method: string;
  };
  relevance: {
    pass: boolean;
    missing_aspects: string[];
    unsupported_claims: string[];
  };
  compliance: {
    pass: boolean;
    rule_ids: string[];
    violations: { rule_id: string; violation: string }[];
  };
}
export interface ProposalAttempt {
  department_id: string;
  version: number;
  draft: { content: string; open_questions: string[]; currency: string | null };
  evaluation: ProposalEvaluation | null;
}
export interface ProposalRun {
  state: string;
  runs: number;
  progress: Record<
    string,
    { phase: string; attempt: number; max_attempts: number }
  >;
  attempts: ProposalAttempt[];
  can_retry: boolean;
  stalled: boolean;
  error_message: string | null;
  handoff: { ready_for_part3: boolean } | null;
}
