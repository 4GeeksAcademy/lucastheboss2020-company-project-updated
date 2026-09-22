/**
 * GET /api/incidents/results/export
 * 
 * Exports the most recent analysis result as a downloadable CSV file.
 */

import { NextResponse } from 'next/server';
import { listAnalyses } from '../../data';

export async function GET(): Promise<NextResponse> {
  try {
    const analyses = listAnalyses(1);

    if (analyses.length === 0) {
      return NextResponse.json(
        { error: 'No analysis results available. Please run an analysis first.' },
        { status: 404 }
      );
    }

    const analysis = analyses[0];

    // Generate CSV content
    const csvLines: string[] = [];
    csvLines.push('Metric,Value');
    csvLines.push('');
    csvLines.push('SUMMARY METRICS,');
    csvLines.push(`Total Records Processed,${analysis.metrics.total_processed}`);
    csvLines.push(`Valid Records,${analysis.metrics.valid_records}`);
    csvLines.push(`Invalid Records,${analysis.metrics.invalid_records}`);
    csvLines.push('');
    csvLines.push('CATEGORY BREAKDOWN,');
    csvLines.push(`Complaints,${analysis.metrics.category_breakdown.complaints}`);
    csvLines.push(`Requests,${analysis.metrics.category_breakdown.requests}`);
    csvLines.push(`Operational Failures,${analysis.metrics.category_breakdown.operational_failures}`);
    csvLines.push('');
    csvLines.push('STATUS BREAKDOWN,');
    csvLines.push(`Open,${analysis.metrics.status_breakdown.open}`);
    csvLines.push(`Closed,${analysis.metrics.status_breakdown.closed}`);
    csvLines.push(`Discarded,${analysis.metrics.status_breakdown.discarded}`);
    csvLines.push('');

    if (analysis.metrics.average_satisfaction_index !== undefined) {
      csvLines.push(`Average Satisfaction Index,${analysis.metrics.average_satisfaction_index.toFixed(2)}`);
    } else {
      csvLines.push('Average Satisfaction Index,N/A');
    }

    if (analysis.invalid_records.length > 0) {
      csvLines.push('');
      csvLines.push('INVALID RECORDS,');
      csvLines.push('Row Number,Incident ID,Errors');
      for (const invalid of analysis.invalid_records) {
        const errorText = invalid.errors.join(' | ');
        const escapedErrors = `"${errorText.replace(/"/g, '""')}"`;
        csvLines.push(`${invalid.row_number},${invalid.incident_id},${escapedErrors}`);
      }
    }

    const csvContent = csvLines.join('\n');
    const timestamp = new Date(analysis.timestamp).toISOString().split('T')[0];
    const filename = `incident-analysis-${timestamp}-latest.csv`;

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