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

  /**
   * Aggregate invalid record errors by type for the red alert display.
   * Groups similar error messages to show "how many of each type".
   * Handles both TRF and legacy format error types.
   */
  function aggregateErrorsByType(invalidRecords: AnalysisResult['invalid_records']): { type: string; count: number }[] {
    const errorCounts: Record<string, number> = {};

    for (const record of invalidRecords) {
      for (const err of record.errors) {
        // Categorize the error message into a type
        let type = 'Other';
        const errLower = err.toLowerCase();

        if (errLower.includes('missing required field') || errLower.includes('missing field')) {
          const match = err.match(/'([^']+)'/);
          type = match ? `Missing field: ${match[1]}` : 'Missing required field';
        } else if (errLower.includes('carrier')) {
          type = 'Invalid carrier';
        } else if (errLower.includes('email')) {
          type = 'Invalid email';
        } else if (errLower.includes('weight') || errLower.includes('weight_kg')) {
          type = 'Invalid weight';
        } else if (errLower.includes('declared_value') || errLower.includes('declared value')) {
          type = 'Invalid declared value';
        } else if (errLower.includes('date')) {
          type = 'Invalid date';
        } else if (errLower.includes('category')) {
          type = 'Invalid category';
        } else if (errLower.includes('status')) {
          type = 'Invalid status';
        } else if (errLower.includes('satisfaction') || errLower.includes('score')) {
          type = 'Invalid satisfaction score';
        }

        errorCounts[type] = (errorCounts[type] || 0) + 1;
      }
    }

    return Object.entries(errorCounts)
      .map(([type, count]) => ({ type, count }))
      .sort((a, b) => b.count - a.count); // Most frequent first
  }

  const displayAnalysis = analysis || (selectedHistoryId && history.find((h) => h.id === selectedHistoryId));

  if (displayAnalysis) {
    const { metrics } = displayAnalysis;
    const m = metrics as any;

    // Detect format: TRF has carrier_breakdown, legacy has category_breakdown with complaints
    const isTRF = m.carrier_breakdown !== undefined;

    return (
      <section>
        <header className="page-header">
          <span className="badge green">Incident Analysis</span>
          <h1>Analysis Results {isTRF ? '(TRF Format)' : ''}</h1>
          <p>File: <strong>{displayAnalysis.filename}</strong></p>
          <div className="actions">
            <button className="button" onClick={handleExport} type="button">Export CSV</button>
            <button className="button secondary" onClick={handleNewAnalysis} type="button">New Analysis</button>
          </div>
        </header>

        <div className="candidate-grid">
          <article className="panel">
            <h3>Summary</h3>
            <div className="stat-group">
              <div className="stat"><span className="stat-value">{m.total_processed}</span><span className="stat-label">Total Records</span></div>
              <div className="stat"><span className="stat-value green">{m.valid_records}</span><span className="stat-label">Valid</span></div>
              <div className="stat"><span className="stat-value red">{m.invalid_records}</span><span className="stat-label">Invalid</span></div>
            </div>
          </article>

          {isTRF && m.carrier_breakdown && (
            <article className="panel">
              <h3>Carrier Breakdown</h3>
              <div className="stat-group">
                {Object.entries(m.carrier_breakdown as Record<string, number>).map(([carrier, count]) => (
                  <div className="stat" key={carrier}>
                    <span className="stat-value">{count}</span>
                    <span className="stat-label">{carrier}</span>
                  </div>
                ))}
              </div>
            </article>
          )}

          <article className="panel">
            <h3>{isTRF ? 'Incident Category' : 'Category'} Breakdown</h3>
            <div className="stat-group">
              {m.category_breakdown && Object.entries(m.category_breakdown as Record<string, number>).map(([cat, count]) => (
                <div className="stat" key={cat}>
                  <span className="stat-value">{count}</span>
                  <span className="stat-label">{cat}</span>
                </div>
              ))}
            </div>
          </article>

          <article className="panel">
            <h3>Status Breakdown</h3>
            <div className="stat-group">
              {m.status_breakdown && Object.entries(m.status_breakdown as Record<string, number>).map(([status, count]) => (
                <div className="stat" key={status}>
                  <span className="stat-value">{count}</span>
                  <span className="stat-label">{status}</span>
                </div>
              ))}
            </div>
          </article>

          {isTRF && m.average_declared_value !== undefined && (
            <article className="panel">
              <h3>Average Declared Value</h3>
              <div className="stat-group">
                <div className="stat"><span className="stat-value">€{m.average_declared_value.toFixed(2)}</span><span className="stat-label">Avg Declared Value</span></div>
              </div>
            </article>
          )}

          {!isTRF && m.average_satisfaction_index !== undefined && (
            <article className="panel">
              <h3>Customer Satisfaction</h3>
              <div className="stat-group">
                <div className="stat"><span className="stat-value">{m.average_satisfaction_index.toFixed(2)}</span><span className="stat-label">Avg Satisfaction (0–10)</span></div>
              </div>
            </article>
          )}
        </div>

        {displayAnalysis.invalid_records.length > 0 && (
          <>
            {/* Red alert banner with error type breakdown */}
            <div className="panel message error" style={{ marginTop: "1rem" }}>
              <h3>⚠️ {displayAnalysis.invalid_records.length} Invalid Record{displayAnalysis.invalid_records.length !== 1 ? 's' : ''} Found</h3>
              <p>The file contains records with validation errors. Please review and correct them.</p>
              <div style={{ marginTop: '0.5rem', display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                {aggregateErrorsByType(displayAnalysis.invalid_records).map(({ type, count }) => (
                  <span key={type} className="badge" style={{ background: '#dc2626', color: '#fff', fontSize: '0.85rem' }}>
                    {count}x {type}
                  </span>
                ))}
              </div>
            </div>

            {/* Expandable details */}
            <section className="panel" style={{ marginTop: "1rem" }}>
              <header>
                <h3>Invalid Records Details ({displayAnalysis.invalid_records.length})</h3>
                <button className="button secondary compact-button" onClick={() => setExpandedInvalidRecords(!expandedInvalidRecords)} type="button">
                  {expandedInvalidRecords ? 'Collapse' : 'Expand'}
                </button>
              </header>
              {expandedInvalidRecords && (
                <div className="detail-grid">
                  {displayAnalysis.invalid_records.map((record) => {
                    const rec = record as any;
                    const idField = isTRF ? rec.tracking_id : rec.incident_id;
                    return (
                      <article className="candidate-card" key={rec.row_number}>
                        <p><strong>Row {rec.row_number}</strong> · ID: {idField || 'N/A'}</p>
                        <ul>
                          {rec.errors.map((error: string) => <li key={error}>{error}</li>)}
                        </ul>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          </>
        )}
      </section>
    );
  }

  return (
    <section>
      <header className="page-header">
        <span className="badge green">Incident Analysis</span>
        <h1>Incident Analysis</h1>
        <p>Upload and analyze customer support incident CSV files</p>
      </header>

      {error && (
        <div className="panel message error">
          <h3>{error.message}</h3>
          {error.details && <p>{error.details}</p>}
        </div>
      )}

      <section className="panel">
        <h2>Upload CSV File</h2>
        {loading && <p className="message loading">Analyzing incidents...</p>}

        <div
          className={`drop-zone ${dragOver ? 'drag-over' : ''}`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
        >
          <p>Drag and drop a CSV file here, or click to select one</p>
          <input
            type="file"
            accept=".csv"
            onChange={handleFileInputChange}
            disabled={loading}
            style={{ marginTop: '1rem' }}
          />
        </div>
      </section>

      {history.length > 0 && (
        <section className="panel" style={{ marginTop: '1rem' }}>
          <h2>Previous Analyses</h2>
          <div className="detail-grid">
            {history.map((item) => (
              <button
                key={item.id}
                className={`candidate-card ${selectedHistoryId === item.id ? 'selected' : ''}`}
                onClick={() => handleLoadFromHistory(item.id)}
                type="button"
                style={{ cursor: 'pointer', textAlign: 'left', width: '100%' }}
              >
                <p><strong>{item.filename}</strong></p>
                <p>{new Date(item.timestamp).toLocaleString()} · {item.metrics.total_processed} records</p>
              </button>
            ))}
          </div>
        </section>
      )}
    </section>
  );
}