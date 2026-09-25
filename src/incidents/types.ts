/**
 * Incident Analysis Domain Types — TrackFlow TRF (Tracking Record Format)
 *
 * Defines tracking/logistics incident records for TrackFlow data analysis:
 * carrier exceptions, lost parcels, delays, damages, etc.
 */

// TrackFlow carriers (US: UPS, FedEx, DHL; Spain: MRW, SEUR, DHL)
export type Carrier = 'UPS' | 'FedEx' | 'DHL' | 'MRW' | 'SEUR';

// TRF incident categories (logistics exception types)
export type TRFCategory =
  | 'LOST_PARCEL'
  | 'DELAYED'
  | 'DAMAGED'
  | 'RETURNED'
  | 'WRONG_ITEM'
  | 'ADDRESS_ISSUE'
  | 'MISSING_LABEL'
  | 'CUSTOMER_CANCELLATION';

// TRF record status lifecycle
export type TRFStatus = 'open' | 'closed' | 'exception';

/**
 * A single TRF (Tracking Record Format) record from the CSV file
 */
export interface TRFRecord {
  tracking_id: string;
  carrier: Carrier;
  category: TRFCategory;
  status: TRFStatus;
  origin: string;
  destination: string;
  shipment_date: string;
  delivery_date?: string;
  weight_kg: number;
  declared_value: number;
  customer_name: string;
  customer_email: string;
  notes?: string;
}

/**
 * Validation error for a single record
 */
export interface RecordValidationError {
  row_number: number;
  tracking_id?: string;
  errors: string[]; // Array of specific field validation errors
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
  average_declared_value?: number;
}

/**
 * Complete analysis result from running the analyzer on a TRF CSV file
 */
export interface AnalysisResult {
  id: string;
  timestamp: number; // Unix milliseconds
  filename: string;
  format?: string; // 'TRF' for TRF format, undefined for legacy
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