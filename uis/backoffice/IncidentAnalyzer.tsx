'use client';

import React, { useState, useCallback } from 'react';
import type { AnalysisResult } from '../../src/incidents/types';

type AnalysisState = AnalysisResult | null;

interface UploadError {
  message: string;
  details?: string;
}

export function IncidentAnalyzer() {
  const [analysis, setAnalysis] = useState<AnalysisState>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<UploadError | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [expandedInvalidRecords, setExpandedInvalidRecords] = useState(false);
  const [history, setHistory] = useState<AnalysisResult[]>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);

  // Fetch analysis history on mount
  React.useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const response = await fetch('/api/incidents/results');
      if (response.ok) {
        const data = await response.json();
        setHistory(data.analyses || []);
      }
    } catch (err) {
      console.error('Failed to load analysis history:', err);
    }
  };

  const handleFileUpload = useCallback(
    async (file: File) => {
      if (!file) {
        setError({ message: 'No file selected' });
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/incidents/analyze', {
          method: 'POST',
          body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
          setError({
            message: 'Upload failed',
            details: data.errors?.[0] || 'Unknown error',
          });
          return;
        }

        if (data.analysis) {
          setAnalysis(data.analysis);
          setSelectedHistoryId(null);
          // Reload history
          await loadHistory();
        }
      } catch (err) {
        setError({
          message: 'Error uploading file',
          details: err instanceof Error ? err.message : 'Unknown error',
        });
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragOver(false);

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        handleFileUpload(files[0]);
      }
    },
    [handleFileUpload]
  );

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.currentTarget.files;
    if (files && files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const handleExport = async () => {
    if (!analysis) return;

    try {
      const response = await fetch(`/api/incidents/results/${analysis.id}/export`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download =
          response.headers
            .get('content-disposition')
            ?.split('filename="')[1]
            ?.replace('"', '') || `incident-analysis-${analysis.id}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (err) {
      console.error('Export failed:', err);
      setError({
        message: 'Export failed',
        details: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  };

  const handleLoadFromHistory = async (id: string) => {
    try {
      const response = await fetch(`/api/incidents/results?id=${id}`);
      if (response.ok) {
        const data = await response.json();
        if (data.analyses && data.analyses.length > 0) {
          setAnalysis(data.analyses[0]);
          setSelectedHistoryId(id);
          setError(null);
        }
      }
    } catch (err) {
      console.error('Failed to load analysis:', err);
    }
  };

  const handleNewAnalysis = () => {
    setAnalysis(null);
    setError(null);
    setSelectedHistoryId(null);
  };

  const displayAnalysis = analysis || (selectedHistoryId && history.find((h) => h.id === selectedHistoryId));

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-4xl">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Incident Analysis</h1>
          <p className="text-gray-600">Upload and analyze customer support incident CSV files</p>
        </div>

        {/* Upload Section */}
        {!displayAnalysis && (
          <div className="bg-white rounded-lg shadow-md p-8 mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Upload CSV File</h2>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-6">
                <h3 className="font-semibold text-red-800">{error.message}</h3>
                {error.details && <p className="text-red-700 text-sm mt-1">{error.details}</p>}
              </div>
            )}

            {loading && (
              <div className="bg-blue-50 border border-blue-200 rounded-md p-4 mb-6">
                <div className="flex items-center">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600 mr-3"></div>
                  <span className="text-blue-700">Processing your file...</span>
                </div>
              </div>
            )}

            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition ${
                dragOver
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <label className="cursor-pointer">
                <div className="flex flex-col items-center">
                  <svg
                    className="h-12 w-12 text-gray-400 mb-3"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 4v16m8-8H4"
                    />
                  </svg>
                  <span className="text-gray-700 font-medium">
                    Drag and drop your CSV file here, or click to select
                  </span>
                  <span className="text-gray-500 text-sm mt-1">
                    CSV files up to 50 MB
                  </span>
                </div>
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileInputChange}
                  className="hidden"
                  disabled={loading}
                />
              </label>
            </div>
          </div>
        )}

        {/* Analysis Results Section */}
        {displayAnalysis && (
          <div className="space-y-6">
            {/* Header */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">Analysis Results</h2>
                  <p className="text-gray-600 text-sm mt-1">
                    File: {displayAnalysis.filename} •{' '}
                    {new Date(displayAnalysis.timestamp).toLocaleString()}
                  </p>
                </div>
                <button
                  onClick={handleNewAnalysis}
                  className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition"
                >
                  Upload New
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-gray-50 rounded-md p-4">
                  <div className="text-gray-600 text-sm font-medium">Total Records</div>
                  <div className="text-3xl font-bold text-gray-900">
                    {displayAnalysis.metrics.total_processed}
                  </div>
                </div>
                <div className="bg-green-50 rounded-md p-4">
                  <div className="text-green-700 text-sm font-medium">Valid Records</div>
                  <div className="text-3xl font-bold text-green-700">
                    {displayAnalysis.metrics.valid_records}
                  </div>
                </div>
                <div className="bg-red-50 rounded-md p-4">
                  <div className="text-red-700 text-sm font-medium">Invalid Records</div>
                  <div className="text-3xl font-bold text-red-700">
                    {displayAnalysis.metrics.invalid_records}
                  </div>
                </div>
              </div>
            </div>

            {/* Category Breakdown */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Breakdown by Category</h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-gray-700">Complaints</span>
                  <span className="font-semibold text-gray-900">
                    {displayAnalysis.metrics.category_breakdown.complaints}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-700">Requests</span>
                  <span className="font-semibold text-gray-900">
                    {displayAnalysis.metrics.category_breakdown.requests}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-700">Operational Failures</span>
                  <span className="font-semibold text-gray-900">
                    {displayAnalysis.metrics.category_breakdown.operational_failures}
                  </span>
                </div>
              </div>
            </div>

            {/* Status Breakdown */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Breakdown by Status</h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-gray-700">Open</span>
                  <span className="font-semibold text-gray-900">
                    {displayAnalysis.metrics.status_breakdown.open}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-700">Closed</span>
                  <span className="font-semibold text-gray-900">
                    {displayAnalysis.metrics.status_breakdown.closed}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-700">Discarded</span>
                  <span className="font-semibold text-gray-900">
                    {displayAnalysis.metrics.status_breakdown.discarded}
                  </span>
                </div>
              </div>
            </div>

            {/* Satisfaction Index */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Customer Satisfaction</h3>
              {displayAnalysis.metrics.average_satisfaction_index !== undefined ? (
                <div className="flex items-center">
                  <div className="text-4xl font-bold text-blue-600">
                    {displayAnalysis.metrics.average_satisfaction_index.toFixed(1)}
                  </div>
                  <div className="ml-4 text-gray-600">out of 10</div>
                </div>
              ) : (
                <div className="text-gray-600">No satisfaction scores recorded</div>
              )}
            </div>

            {/* Invalid Records */}
            {displayAnalysis.invalid_records.length > 0 && (
              <div className="bg-white rounded-lg shadow-md p-6">
                <button
                  onClick={() => setExpandedInvalidRecords(!expandedInvalidRecords)}
                  className="w-full flex justify-between items-center"
                >
                  <h3 className="text-lg font-semibold text-gray-900">
                    Invalid Records ({displayAnalysis.invalid_records.length})
                  </h3>
                  <svg
                    className={`h-5 w-5 text-gray-400 transform transition ${
                      expandedInvalidRecords ? 'rotate-180' : ''
                    }`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 14l-7 7m0 0l-7-7m7 7V3"
                    />
                  </svg>
                </button>

                {expandedInvalidRecords && (
                  <div className="mt-4 space-y-3 max-h-96 overflow-y-auto">
                    {displayAnalysis.invalid_records.map((record: any, idx: number) => (
                      <div
                        key={idx}
                        className="bg-red-50 border border-red-200 rounded-md p-4"
                      >
                        <div className="font-semibold text-red-900">
                          Row {record.row_number} (ID: {record.incident_id})
                        </div>
                        <ul className="mt-2 space-y-1">
                          {record.errors.map((error: string, errorIdx: number) => (
                            <li key={errorIdx} className="text-red-700 text-sm">
                              • {error}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Export Button */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <button
                onClick={handleExport}
                className="w-full px-6 py-3 bg-green-600 text-white font-semibold rounded-md hover:bg-green-700 transition flex items-center justify-center"
              >
                <svg
                  className="h-5 w-5 mr-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                  />
                </svg>
                Export Results as CSV
              </button>
            </div>
          </div>
        )}

        {/* History Section */}
        {history.length > 0 && (
          <div className="mt-12 bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Analysis History</h2>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {history.map((item) => (
                <button
                  key={item.id}
                  onClick={() => handleLoadFromHistory(item.id)}
                  className={`w-full text-left px-4 py-3 rounded-md border transition ${
                    selectedHistoryId === item.id
                      ? 'bg-blue-50 border-blue-300'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  <div className="font-medium text-gray-900">{item.filename}</div>
                  <div className="text-sm text-gray-600">
                    {new Date(item.timestamp).toLocaleString()} •{' '}
                    {item.metrics.total_processed} records
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
