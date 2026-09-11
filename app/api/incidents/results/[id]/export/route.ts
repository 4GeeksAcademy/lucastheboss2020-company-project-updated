/**
 * GET /api/incidents/results/[id]/export
 * 
 * Exports a specific analysis result as a downloadable CSV file
 */

import { NextResponse } from 'next/server';
import { getAnalysis } from '../../../data';

export async function GET(
  _request: unknown,
  { params }: { params: { id: string } }
): Promise<NextResponse> {
  try {
    const { id } = params;

    const analysis = getAnalysis(id);

    if (!analysis) {
      return NextResponse.json(
        { error: `Analysis with ID ${id} not found` },
        { status: 404 }
      );
    }

    // Generate CSV content
    const csvLines: string[] = [];
    csvLines.push('Metric,Value');
    csvLines.push(''); // Blank line

    // Summary metrics
    csvLines.push('SUMMARY METRICS,');
    csvLines.push(
      `Total Records Processed,${analysis.metrics.total_processed}`
    );
    csvLines.push(`Valid Records,${analysis.metrics.valid_records}`);
    csvLines.push(`Invalid Records,${analysis.metrics.invalid_records}`);

    csvLines.push(''); // Blank line

    // Category breakdown
    csvLines.push('CATEGORY BREAKDOWN,');
    csvLines.push(
      `Complaints,${analysis.metrics.category_breakdown.complaints}`
    );
    csvLines.push(`Requests,${analysis.metrics.category_breakdown.requests}`);
    csvLines.push(
      `Operational Failures,${analysis.metrics.category_breakdown.operational_failures}`
    );

    csvLines.push(''); // Blank line

    // Status breakdown
    csvLines.push('STATUS BREAKDOWN,');
    csvLines.push(`Open,${analysis.metrics.status_breakdown.open}`);
    csvLines.push(`Closed,${analysis.metrics.status_breakdown.closed}`);
    csvLines.push(`Discarded,${analysis.metrics.status_breakdown.discarded}`);

    csvLines.push(''); // Blank line

    // Satisfaction index
    if (analysis.metrics.average_satisfaction_index !== undefined) {
      csvLines.push(
        `Average Satisfaction Index,${analysis.metrics.average_satisfaction_index.toFixed(2)}`
      );
    } else {
      csvLines.push('Average Satisfaction Index,N/A');
    }

    // Invalid records details
    if (analysis.invalid_records.length > 0) {
      csvLines.push(''); // Blank line
      csvLines.push('INVALID RECORDS,');
      csvLines.push('Row Number,Incident ID,Errors');

      for (const invalid of analysis.invalid_records) {
        const errorText = invalid.errors.join(' | ');
        const escapedErrors = `"${errorText.replace(/"/g, '""')}"`;
        csvLines.push(
          `${invalid.row_number},${invalid.incident_id},${escapedErrors}`
        );
      }
    }

    const csvContent = csvLines.join('\n');

    // Generate filename with timestamp
    const timestamp = new Date(analysis.timestamp).toISOString().split('T')[0];
    const filename = `incident-analysis-${timestamp}-${id.substring(0, 8)}.csv`;

    // Return CSV file as downloadable attachment
    return new NextResponse(csvContent, {
      status: 200,
      headers: {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': `attachment; filename="${filename}"`,
      },
    });
  } catch (error) {
    console.error('Error exporting analysis:', error);
    return NextResponse.json(
      { error: 'Failed to export analysis' },
      { status: 500 }
    );
  }
}
