/**
 * Incident Analysis Domain Types — TrackFlow Syllabus Format
 *
 * Defines incident records per CONTEXT.md TrackFlow spec:
 * incident_id, category (complaints/requests/operational_failures),
 * status (open/closed/discarded), description, customer_name, email,
 * phone, date, satisfaction_score (0-10), notes.
 */

// TrackFlow incident categories (per CONTEXT syllabus)
export type TrackFlowCategory =
  | 'complaints'
  | 'requests'
  | 'operational_failures';

// TrackFlow incident statuses
export type TrackFlowStatus = 'open' | 'closed' | 'discarded';

/**
 * A single incident record from the CSV file (Syllabus Format)
 */
export interface IncidentRecord {
  incident_id: string;
  category: TrackFlowCategory;
  status: TrackFlowStatus;
  description: string;
  customer_name: string;
  email: string;
  phone?: string;
  date: string;
  satisfaction_score?: number;
  notes?: string;
}

/**
 * Validation error for a single record
 */
export interface RecordValidationError {
  row_number: number;
  incident_id?: string;
  errors: string[];
}

/**
 * Metrics calculated from valid records
 */
export interface AnalysisMetrics {
  total_processed: number;
  valid_records: number;
  invalid_records: number;
  category_breakdown: Record<string, number>;
  status_breakdown: Record<string, number>;
  average_satisfaction_index?: number;
}

/**
 * Complete analysis result from running the analyzer on a CSV file
 */
export interface AnalysisResult {
  id: string;
  timestamp: number;
  filename: string;
  format?: string;
  metrics: AnalysisMetrics;
  invalid_records: RecordValidationError[];
  valid_record_count: number;
}

/**
 * API response for analyze endpoint
 */
export interface AnalyzeResponse {
  analysis?: AnalysisResult;
  errors?: string[];
}

/**
 * API response for results retrieval
 */
export interface ResultsResponse {
  analyses: AnalysisResult[];
}