/**
 * GET /api/incidents/results/[id]/export
 *
 * Exports a specific analysis result as a downloadable CSV file
 * Supports both TRF format and legacy format.
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

    const metrics = analysis.metrics as any;

    // Use 'trackflow' format detection: average_satisfaction_index present means trackflow
    const isTrackflow = 'average_satisfaction_index' in metrics || !('carrier_breakdown' in metrics);

    csvLines.push(''); // Blank line

    // Summary metrics
    csvLines.push('SUMMARY METRICS,');
    csvLines.push(`Format,${isTrackflow ? 'TrackFlow' : 'Legacy'}`);
    csvLines.push(`Total Records Processed,${metrics.total_processed}`);
    csvLines.push(`Valid Records,${metrics.valid_records}`);
    csvLines.push(`Invalid Records,${metrics.invalid_records}`);

    csvLines.push(''); // Blank line

    // Category breakdown
    csvLines.push('CATEGORY BREAKDOWN,');
    if (metrics.category_breakdown) {
      for (const [cat, count] of Object.entries(metrics.category_breakdown)) {
        const label = cat.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        csvLines.push(`${label},${count}`);
      }
    }

    csvLines.push(''); // Blank line

    // Status breakdown
    csvLines.push('STATUS BREAKDOWN,');
    if (metrics.status_breakdown) {
      for (const [status, count] of Object.entries(metrics.status_breakdown)) {
        csvLines.push(`${status.charAt(0).toUpperCase() + status.slice(1)},${count}`);
      }
    }

    csvLines.push(''); // Blank line

    // Average satisfaction index
    const avgSat = metrics.average_satisfaction_index;
    csvLines.push(`Average Satisfaction Index,${avgSat !== undefined ? avgSat.toFixed(2) : 'N/A'}`);

    // Invalid records details
    if (analysis.invalid_records.length > 0) {
      csvLines.push(''); // Blank line
      csvLines.push('INVALID RECORDS,');
      csvLines.push('Row Number,Incident ID,Errors');

      for (const invalid of analysis.invalid_records) {
        const errorText = invalid.errors.join(' | ');
        const escapedErrors = `"${errorText.replace(/"/g, '""')}"`;
        const recId = (invalid as any).incident_id || (invalid as any).tracking_id || 'N/A';
        csvLines.push(`${invalid.row_number},${recId},${escapedErrors}`);
      }
    }

    const csvContent = csvLines.join('\n');

    // Generate filename with timestamp
    const timestamp = new Date(analysis.timestamp).toISOString().split('T')[0];
    const formatTag = isTrackflow ? 'trackflow' : 'legacy';
    const filename = `incident-analysis-${formatTag}-${timestamp}-${id.substring(0, 8)}.csv`;

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