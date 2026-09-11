/**
 * In-Memory Storage for Incident Analysis Results
 * Mirrors the pattern used in app/api/candidates/data.ts
 */

import type { AnalysisResult } from '../../../src/incidents/types';
import { randomUUID } from 'crypto';

// In-memory store - survives session but not server restart
const analysisResults: Map<string, AnalysisResult> = new Map();

/**
 * Store a new analysis result
 */
export function storeAnalysis(analysis: Omit<AnalysisResult, 'id' | 'timestamp'>): AnalysisResult {
  const id = randomUUID();
  const timestamp = Date.now();

  const result: AnalysisResult = {
    ...analysis,
    id,
    timestamp,
  };

  analysisResults.set(id, result);
  return result;
}

/**
 * Retrieve a specific analysis result by ID
 */
export function getAnalysis(id: string): AnalysisResult | null {
  return analysisResults.get(id) || null;
}

/**
 * List all stored analysis results, optionally limited
 */
export function listAnalyses(limit?: number): AnalysisResult[] {
  // Sort by timestamp descending (newest first)
  const all = Array.from(analysisResults.values()).sort(
    (a, b) => b.timestamp - a.timestamp
  );

  if (limit) {
    return all.slice(0, limit);
  }

  return all;
}

/**
 * Delete an analysis result by ID
 */
export function deleteAnalysis(id: string): boolean {
  return analysisResults.delete(id);
}

/**
 * Clear all analysis results
 */
export function clearAllAnalyses(): void {
  analysisResults.clear();
}

/**
 * Get statistics about stored analyses
 */
export function getAnalysisStats(): {
  total_analyses: number;
  total_records_analyzed: number;
  total_invalid_records: number;
} {
  let totalRecordsAnalyzed = 0;
  let totalInvalidRecords = 0;

  analysisResults.forEach((analysis) => {
    totalRecordsAnalyzed += analysis.metrics.total_processed;
    totalInvalidRecords += analysis.metrics.invalid_records;
  });

  return {
    total_analyses: analysisResults.size,
    total_records_analyzed: totalRecordsAnalyzed,
    total_invalid_records: totalInvalidRecords,
  };
}
