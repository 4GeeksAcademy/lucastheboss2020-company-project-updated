/**
 * POST /api/incidents/analyze
 *
 * Accepts a CSV file upload containing TrackFlow incident records.
 * Spawns the Python analysis script as a subprocess, parses results,
 * stores them in memory, and returns the analysis.
 */

import { NextRequest, NextResponse } from 'next/server';
import { writeFile, unlink } from 'fs/promises';
import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import os from 'os';
import { randomUUID } from 'crypto';
import { storeAnalysis } from '../data';
import type { AnalyzeResponse } from '../../../../src/incidents/types';

const execFileAsync = promisify(execFile);

// Configuration
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB
const ALLOWED_MIME_TYPES = ['text/csv', 'application/vnd.ms-excel'];
const PYTHON_SCRIPT = path.join(process.cwd(), 'scripts/analyze_incidents.py');

interface PythonAnalysisOutput {
  format: string;
  total_processed: number;
  valid_records: number;
  invalid_records: number;
  category_breakdown: Record<string, number>;
  status_breakdown: Record<string, number>;
  average_satisfaction_index: number | null;
  invalid_record_details: Array<{
    row_number: number;
    incident_id: string;
    errors: string[];
  }>;
}

export async function POST(request: NextRequest): Promise<NextResponse<AnalyzeResponse>> {
  try {
    // Parse multipart form data
    const formData = await request.formData();
    const file = formData.get('file') as File | null;

    if (!file) {
      return NextResponse.json(
        { errors: ['No file provided. Please upload a CSV file.'] },
        { status: 400 }
      );
    }

    // Validate file type
    if (!ALLOWED_MIME_TYPES.includes(file.type) && !file.name.endsWith('.csv')) {
      return NextResponse.json(
        { errors: [`Invalid file type. Expected CSV file, got: ${file.type}`] },
        { status: 400 }
      );
    }

    // Validate file size
    if (file.size > MAX_FILE_SIZE) {
      return NextResponse.json(
        {
          errors: [
            `File too large. Maximum size is ${MAX_FILE_SIZE / (1024 * 1024)} MB, ` +
            `but your file is ${(file.size / (1024 * 1024)).toFixed(2)} MB.`,
          ],
        },
        { status: 400 }
      );
    }

    if (file.size === 0) {
      return NextResponse.json(
        { errors: ['File is empty. Please upload a CSV file with data.'] },
        { status: 400 }
      );
    }

    // Write file to temp location
    const tempDir = os.tmpdir();
    const tempFileName = `incident-analysis-${randomUUID()}.csv`;
    const tempFilePath = path.join(tempDir, tempFileName);

    const buffer = await file.arrayBuffer();
    await writeFile(tempFilePath, Buffer.from(buffer));

    try {
      // Run Python analysis script
      const { stdout, stderr } = await execFileAsync('python3', [PYTHON_SCRIPT, tempFilePath], {
        maxBuffer: 10 * 1024 * 1024, // 10 MB stdout buffer
        timeout: 60000, // 60 second timeout
      });

      if (stderr) {
        console.error('Python stderr:', stderr);
      }

      // Parse Python output - the script outputs structured data
      const lines = stdout.split('\n');
      let analysisData: PythonAnalysisOutput | null = null;

      // Try to find JSON in the output
      for (const line of lines) {
        if (line.trim().startsWith('{')) {
          try {
            analysisData = JSON.parse(line);
            break;
          } catch {
            // Continue looking
          }
        }
      }

      if (!analysisData) {
        return NextResponse.json(
          { errors: ['Failed to parse analysis results from Python script'] },
          { status: 500 }
        );
      }

      // Create analysis result object and store it (trackflow format)
      const stored = storeAnalysis({
        filename: file.name,
        format: 'trackflow',
        metrics: {
          total_processed: analysisData.total_processed,
          valid_records: analysisData.valid_records,
          invalid_records: analysisData.invalid_records,
          category_breakdown: analysisData.category_breakdown,
          status_breakdown: analysisData.status_breakdown,
          average_satisfaction_index: analysisData.average_satisfaction_index ?? undefined,
        },
        invalid_records: analysisData.invalid_record_details,
        valid_record_count: analysisData.valid_records,
      });

      return NextResponse.json(
        { analysis: stored },
        { status: 200 }
      );
    } finally {
      // Clean up temp file
      try {
        await unlink(tempFilePath);
      } catch (error) {
        console.error('Failed to clean up temp file:', error);
      }
    }
  } catch (error) {
    console.error('Incident analysis error:', error);

    const message = error instanceof Error ? error.message : 'Unknown error';
    const errors = [
      'An error occurred while analyzing the file. ' +
      `Details: ${message}`,
    ];

    if (message.includes('ENOENT')) {
      errors[0] = 'Python script not found. Please ensure the analyze_incidents.py script is in the scripts directory.';
    } else if (message.includes('timeout')) {
      errors[0] = 'Analysis took too long and was cancelled. Please try with a smaller file.';
    }

    return NextResponse.json({ errors }, { status: 500 });
  }
}