/**
 * GET /api/incidents/results
 * 
 * Retrieves stored incident analysis results.
 * Supports optional query parameter: ?id=<analysisId> for specific analysis
 * Otherwise returns the last 50 analyses
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAnalysis, listAnalyses } from '../data';
import type { ResultsResponse } from '../../../../src/incidents/types';

export async function GET(request: NextRequest): Promise<NextResponse<ResultsResponse | { error: string }>> {
  try {
    // Check if specific analysis ID is requested
    const id = request.nextUrl.searchParams.get('id');

    if (id) {
      const analysis = getAnalysis(id);

      if (!analysis) {
        return NextResponse.json(
          { error: `Analysis with ID ${id} not found` },
          { status: 404 }
        );
      }

      return NextResponse.json(
        { analyses: [analysis] },
        { status: 200 }
      );
    }

    // Return last 50 analyses
    const analyses = listAnalyses(50);

    return NextResponse.json(
      { analyses },
      { status: 200 }
    );
  } catch (error) {
    console.error('Error retrieving incident analyses:', error);
    return NextResponse.json(
      { error: 'Failed to retrieve analyses' },
      { status: 500 }
    );
  }
}
