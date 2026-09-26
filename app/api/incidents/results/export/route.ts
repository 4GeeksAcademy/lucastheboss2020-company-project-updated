/**
 * GET /api/incidents/results/export
 *
 * Exports the most recent analysis result as a downloadable CSV file.
 * Supports both TRF format and legacy format.
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
    const m = analysis.metrics as any;
    const isTRF = m.carrier_breakdown !== undefined;

    // Generate CSV content
    const csvLines: string[] = [];
    csvLines.push('Metric,Value');
    csvLines.push('');
    csvLines.push('SUMMARY METRICS,');
    csvLines.push(`Format,${isTRF ? 'TRF' : 'Legacy'}`);
    csvLines.push(`Total Records Processed,${m.total_processed}`);
    csvLines.push(`Valid Records,${m.valid_records}`);
    csvLines.push(`Invalid Records,${m.invalid_records}`);

    csvLines.push('');
    csvLines.push('CARRIER BREAKDOWN,');
    if (isTRF && m.carrier_breakdown) {
      for (const [carrier, count] of Object.entries(m.carrier_breakdown)) {
        csvLines.push(`${carrier},${count}`);
      }
    }

    csvLines.push('');
    csvLines.push('CATEGORY BREAKDOWN,');
    if (m.category_breakdown) {
      for (const [cat, count] of Object.entries(m.category_breakdown)) {
        csvLines.push(`${cat},${count}`);
      }
    }

    csvLines.push('');
    csvLines.push('STATUS BREAKDOWN,');
    if (m.status_breakdown) {
      for (const [status, count] of Object.entries(m.status_breakdown)) {
        csvLines.push(`${status},${count}`);
      }
    }

    csvLines.push('');

    if (isTRF) {
      csvLines.push(`Average Declared Value (€),${m.average_declared_value?.toFixed(2) || 'N/A'}`);
    } else {
      csvLines.push(`Average Satisfaction Index,${m.average_satisfaction_index?.toFixed(2) || 'N/A'}`);
    }

    if (analysis.invalid_records.length > 0) {
      csvLines.push('');
      csvLines.push('INVALID RECORDS,');
      const idField = isTRF ? 'Tracking ID' : 'Incident ID';
      csvLines.push(`Row Number,${idField},Errors`);
      for (const invalid of analysis.invalid_records) {
        const errorText = invalid.errors.join(' | ');
        const escapedErrors = `"${errorText.replace(/"/g, '""')}"`;
        const recId = (invalid as any).tracking_id || (invalid as any).incident_id || 'N/A';
        csvLines.push(`${invalid.row_number},${recId},${escapedErrors}`);
      }
    }

    const csvContent = csvLines.join('\n');
    const timestamp = new Date(analysis.timestamp).toISOString().split('T')[0];
    const formatTag = isTRF ? 'trf' : 'legacy';
    const filename = `incident-analysis-${formatTag}-${timestamp}-latest.csv`;

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