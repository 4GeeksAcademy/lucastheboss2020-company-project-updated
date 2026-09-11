/**
 * Incident Analysis Domain Types
 * 
 * Defines incident records for customer support data analysis:
 * complaints, requests, and operational failures.
 */

// Incident categories from the support department system
export type IncidentCategory = 'complaints' | 'requests' | 'operational_failures';

// Incident status lifecycle
export type IncidentStatus = 'open' | 'closed' | 'discarded';

/**
 * A single incident record from the CSV file
 */
export interface IncidentRecord {
  incident_id: string;
  category: IncidentCategory;
  status: IncidentStatus;
  description: string;
  customer_name: string;
  email: string;
  phone?: string;
  date: string;
  satisfaction_score?: number; // Only for closed incidents
  notes?: string;
}

/**
 * Validation error for a single record
 */
export interface RecordValidationError {
  row_number: number;
  incident_id?: string;
  errors: string[]; // Array of specific field validation errors
}

/**
 * Metrics calculated from valid records
 */
export interface AnalysisMetrics {
  total_processed: number;
  valid_records: number;
  invalid_records: number;
  category_breakdown: {
    complaints: number;
    requests: number;
    operational_failures: number;
  };
  status_breakdown: {
    open: number;
    closed: number;
    discarded: number;
  };
  average_satisfaction_index?: number; // Average of satisfaction scores for closed incidents
  satisfaction_score_count?: number; // Count of closed incidents with satisfaction scores
}

/**
 * Complete analysis result from running the analyzer on a CSV file
 */
export interface AnalysisResult {
  id: string;
  timestamp: number; // Unix milliseconds
  filename: string;
  metrics: AnalysisMetrics;
  invalid_records: RecordValidationError[]; // Details on each invalid record
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
