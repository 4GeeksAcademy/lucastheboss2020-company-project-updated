/**
 * Incident Analysis Domain Types — TrackFlow Logistics Format
 *
 * Defines incident records per CONTEXT-trackflow spec:
 * incident_id (TRF-XXXXXX), date (YYYY-MM-DD), country (US/ES),
 * customer_type (B2B/B2C), tracking_number (>=8 chars),
 * carrier (per country), category (LOST_PARCEL/DELAYED_DELIVERY/etc.),
 * status (OPEN/CLOSED/DISCARDED), customer_email (SENSITIVE),
 * satisfaction_score (1-5, required if CLOSED).
 */

// Valid countries
export type TrackFlowCountry = 'US' | 'ES';

// Valid carriers per country
export type TrackFlowCarrier = 'UPS' | 'FEDEX' | 'DHL_US' | 'MRW' | 'SEUR' | 'DHL_ES' | 'LOCAL_ES';

// Valid incident categories (TrackFlow logistics)
export type TrackFlowCategory =
  | 'LOST_PARCEL'
  | 'DELAYED_DELIVERY'
  | 'WRONG_ADDRESS'
  | 'RETURN_REQUEST'
  | 'DAMAGE';

// Valid incident statuses
export type TrackFlowStatus = 'OPEN' | 'CLOSED' | 'DISCARDED';

// Valid customer types
export type CustomerType = 'B2B' | 'B2C';

/**
 * A single incident record from the CSV file (TrackFlow Format)
 */
export interface TrackFlowRecord {
  incident_id: string;
  date: string;
  country: TrackFlowCountry;
  customer_type: CustomerType;
  tracking_number: string;
  carrier: TrackFlowCarrier;
  category: TrackFlowCategory;
  description: string;
  status: TrackFlowStatus;
  customer_email: string;
  satisfaction_score?: number;
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
  carrier_breakdown: Record<string, number>;
  category_breakdown: Record<string, number>;
  status_breakdown: Record<string, number>;
  country_breakdown: Record<string, number>;
  average_satisfaction_index?: number;
  invalid_breakdown: Record<string, number>;
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