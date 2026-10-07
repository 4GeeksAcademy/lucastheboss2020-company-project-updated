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
  error?: string;
  format: string;
  total_processed: number;
  valid_records: number;
  invalid_records: number;
  carrier_breakdown: Record<string, number>;
  category_breakdown: Record<string, number>;
  status_breakdown: Record<string, number>;
  country_breakdown: Record<string, number>;
  average_satisfaction_index: number | null;
  invalid_breakdown: Record<string, number>;
  invalid_record_details: Array<{
    row_number: number;
    incident_id: string;
    errors: string[];
  }>;
}

function parseAnalyzerOutput(stdout: string): PythonAnalysisOutput | null {
  for (const line of stdout.split("\n")) {
    if (!line.trim().startsWith("{")) continue;
    try {
      return JSON.parse(line) as PythonAnalysisOutput;
    } catch {
      // Continue to the next output line; user-facing errors are handled by the caller.
    }
  }
  return null;
}

function handleSubprocessFailure(error: unknown): NextResponse<AnalyzeResponse> {
  const childError = error as { code?: unknown; killed?: unknown; stdout?: unknown };
  if (typeof childError.stdout === "string") {
    const analysisOutput = parseAnalyzerOutput(childError.stdout);
    if (analysisOutput?.error) {
      return NextResponse.json(
        { errors: ["The uploaded CSV could not be read. Check its format and try again."] },
        { status: 400 },
      );
    }
  }

  const errorCode = typeof childError.code === "string" ? childError.code : "";
  if (errorCode === "ETIMEDOUT" || childError.killed === true) {
    return NextResponse.json(
      { errors: ["Analysis took too long. Try a smaller CSV file."] },
      { status: 504 },
    );
  }
  if (errorCode === "ENOENT") {
    return NextResponse.json(
      { errors: ["The incident analyzer is temporarily unavailable. Please retry later."] },
      { status: 503 },
    );
  }

  console.error("Incident analyzer subprocess failed.");
  return NextResponse.json(
    { errors: ["The file could not be analyzed. Check the CSV and try again."] },
    { status: 500 },
  );
}

export async function POST(request: NextRequest): Promise<NextResponse<AnalyzeResponse>> {
  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json({ errors: ["Request must contain a valid CSV upload."] }, { status: 400 });
  }
  const file = formData.get("file") as File | null;

  if (!file || typeof file.arrayBuffer !== "function") {
    return NextResponse.json(
      { errors: ["No file provided. Please upload a CSV file."] },
      { status: 400 },
    );
  }

  if (!ALLOWED_MIME_TYPES.includes(file.type) && !file.name.toLowerCase().endsWith(".csv")) {
    return NextResponse.json(
      { errors: ["Invalid file type. Please upload a CSV file."] },
      { status: 400 },
    );
  }

  if (file.size > MAX_FILE_SIZE) {
    return NextResponse.json(
      { errors: [`File too large. Maximum size is ${MAX_FILE_SIZE / (1024 * 1024)} MB.`] },
      { status: 413 },
    );
  }

  if (file.size === 0) {
    return NextResponse.json(
      { errors: ["File is empty. Please upload a CSV file with data."] },
      { status: 400 },
    );
  }

  let buffer: ArrayBuffer;
  try {
    buffer = await file.arrayBuffer();
  } catch {
    return NextResponse.json({ errors: ["The uploaded file could not be read. Please retry."] }, { status: 400 });
  }

  const tempFilePath = path.join(os.tmpdir(), `incident-analysis-${randomUUID()}.csv`);
  try {
    try {
      await writeFile(tempFilePath, Buffer.from(buffer));
    } catch {
      console.error("Incident analyzer could not stage the upload.");
      return NextResponse.json(
        { errors: ["The upload could not be processed. Please retry."] },
        { status: 500 },
      );
    }

    let stdout: string;
    let stderr: string;
    try {
      const result = await execFileAsync("python3", [PYTHON_SCRIPT, tempFilePath], {
        maxBuffer: 10 * 1024 * 1024, // 10 MB stdout buffer
        timeout: 60000, // 60 second timeout
      });
      stdout = result.stdout;
      stderr = result.stderr;
    } catch (error) {
      return handleSubprocessFailure(error);
    }

    if (stderr) console.error("Incident analyzer emitted a diagnostic message.");

    const analysisData = parseAnalyzerOutput(stdout);
    if (!analysisData) {
      console.error("Incident analyzer output could not be parsed.");
      return NextResponse.json(
        { errors: ["The analyzer returned an unreadable response. Please retry."] },
        { status: 500 },
      );
    }

    if (analysisData.error) {
      return NextResponse.json(
        { errors: ["The uploaded CSV could not be read. Check its format and try again."] },
        { status: 400 },
      );
    }

    let stored: ReturnType<typeof storeAnalysis>;
    try {
      stored = storeAnalysis({
        filename: file.name,
        format: 'trackflow',
        metrics: {
          total_processed: analysisData.total_processed,
          valid_records: analysisData.valid_records,
          invalid_records: analysisData.invalid_records,
          carrier_breakdown: analysisData.carrier_breakdown,
          category_breakdown: analysisData.category_breakdown,
          status_breakdown: analysisData.status_breakdown,
          country_breakdown: analysisData.country_breakdown,
          average_satisfaction_index: analysisData.average_satisfaction_index ?? undefined,
          invalid_breakdown: analysisData.invalid_breakdown,
        },
        invalid_records: analysisData.invalid_record_details,
        valid_record_count: analysisData.valid_records,
      });
    } catch {
      console.error("Incident analyzer could not store its result.");
      return NextResponse.json(
        { errors: ["Analysis completed but could not be saved. Please retry."] },
        { status: 500 },
      );
    }

    return NextResponse.json({ analysis: stored }, { status: 200 });
  } finally {
    try {
      await unlink(tempFilePath);
    } catch {
      console.error("Incident analyzer temporary-file cleanup failed.");
    }
  }
}