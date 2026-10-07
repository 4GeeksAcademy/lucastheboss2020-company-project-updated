'use client';

import React, { useState, useCallback } from 'react';
import type { AnalysisResult } from '../../src/incidents/types';
import { ApiRequestError, fetchResponse, parseJsonResponse, userSafeErrorMessage } from '../../src/utils/api-errors';

type AnalysisState = AnalysisResult | null;
const STORAGE_KEY = 'trackflow_token';

interface UploadError {
  message: string;
  details?: string;
}

function authHeaders(): HeadersInit {
  if (typeof window === 'undefined') return {};
  const token = localStorage.getItem(STORAGE_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function IncidentAnalyzer() {
  const [analysis, setAnalysis] = useState<AnalysisState>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<UploadError | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [expandedInvalidRecords, setExpandedInvalidRecords] = useState(false);
  const [history, setHistory] = useState<AnalysisResult[]>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [selectedHistoryLoading, setSelectedHistoryLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  function getRequestError(error: unknown, fallback: string): string {
    if (error instanceof ApiRequestError && error.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem(STORAGE_KEY);
      window.location.assign('/login');
    }
    return userSafeErrorMessage(error, fallback);
  }

  // Fetch analysis history on mount
  React.useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const response = await fetchResponse('/api/incidents/results', { headers: { ...authHeaders() } });
      const data = await parseJsonResponse<{ analyses?: AnalysisResult[] }>(response);
      setHistory(Array.isArray(data.analyses) ? data.analyses : []);
    } catch (requestError) {
      setHistoryError(getRequestError(requestError, 'Could not load analysis history. Please retry.'));
    } finally {
      setHistoryLoading(false);
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

        const response = await fetchResponse('/api/incidents/analyze', {
          method: 'POST',
          headers: { ...authHeaders() },
          body: formData,
        });

        const data = await parseJsonResponse<{ analysis?: AnalysisResult; errors?: string[] }>(response);

        if (data.analysis) {
          setAnalysis(data.analysis);
          setSelectedHistoryId(null);
          // Reload history
          await loadHistory();
        } else {
          setError({ message: 'Upload failed', details: 'The analyzer returned no results. Please retry.' });
        }
      } catch (err) {
        setError({
          message: 'Upload failed',
          details: getRequestError(err, 'The file could not be analyzed. Check it and retry.'),
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
      if (loading) return;

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        handleFileUpload(files[0]);
      }
    },
    [handleFileUpload, loading]
  );

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (!loading) setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.currentTarget.files;
    if (files && files.length > 0) {
      handleFileUpload(files[0]);
    }
    e.currentTarget.value = '';
  };

  const handleExport = async () => {
    if (!analysis) return;
    let objectUrl: string | null = null;
    let anchor: HTMLAnchorElement | null = null;
    setExporting(true);
    try {
      const response = await fetchResponse(`/api/incidents/results/${analysis.id}/export`, { headers: { ...authHeaders() } });
      if (!response.ok) await parseJsonResponse<never>(response);
      if (!response.headers.get('content-type')?.toLowerCase().includes('text/csv')) {
        throw new ApiRequestError('The analysis export could not be prepared.', response.status);
      }
      const blob = await response.blob();
      objectUrl = window.URL.createObjectURL(blob);
      anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download =
        response.headers
          .get('content-disposition')
          ?.split('filename="')[1]
          ?.replace('"', '') || `incident-analysis-${analysis.id}.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
    } catch (err) {
      setError({
        message: 'Export failed',
        details: getRequestError(err, 'The analysis export could not be downloaded. Please retry.'),
      });
    } finally {
      if (anchor?.parentNode) anchor.parentNode.removeChild(anchor);
      if (objectUrl) window.URL.revokeObjectURL(objectUrl);
      setExporting(false);
    }
  };

  const handleLoadFromHistory = async (id: string) => {
    setSelectedHistoryLoading(true);
    setError(null);
    try {
      const response = await fetchResponse(`/api/incidents/results?id=${id}`, { headers: { ...authHeaders() } });
      const data = await parseJsonResponse<{ analyses?: AnalysisResult[] }>(response);
      if (data.analyses && data.analyses.length > 0) {
        setAnalysis(data.analyses[0]);
        setSelectedHistoryId(id);
      }
    } catch (requestError) {
      setError({
        message: 'Could not open this analysis',
        details: getRequestError(requestError, 'The saved analysis could not be loaded. Please retry.'),
      });
    } finally {
      setSelectedHistoryLoading(false);
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
        } else if (errLower.includes('tracking') && (errLower.includes('short') || errLower.includes('8 character'))) {
          type = 'Invalid tracking number';
        } else if (errLower.includes('carrier') && (errLower.includes('country') || errLower.includes('valid'))) {
          type = 'Carrier/country mismatch';
        } else if (errLower.includes('category')) {
          type = 'Invalid or missing category';
        } else if (errLower.includes('email')) {
          type = 'Invalid or missing email';
        } else if (errLower.includes('closed') && errLower.includes('satisfaction')) {
          type = 'Closed incident, no score';
        } else if (errLower.includes('satisfaction') || errLower.includes('score')) {
          type = 'Invalid satisfaction score';
        } else if (errLower.includes('description')) {
          type = 'Invalid or missing description';
        } else if (errLower.includes('date')) {
          type = 'Invalid date';
        } else if (errLower.includes('country')) {
          type = 'Invalid or missing country';
        } else if (errLower.includes('customer_type')) {
          type = 'Invalid customer type';
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

    // TrackFlow logistics format has carrier_breakdown
    return (
      <section>
        <header className="page-header">
          <span className="badge green">Incident Analysis</span>
          <h1>TrackFlow Analysis Results</h1>
          <p>File: <strong>{displayAnalysis.filename}</strong></p>
          <div className="actions">
            <button className="button" onClick={handleExport} type="button" disabled={exporting}>
              {exporting ? 'Exporting…' : 'Export CSV'}
            </button>
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

          {m.carrier_breakdown && Object.keys(m.carrier_breakdown).length > 0 && (
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
            <h3>Category Breakdown</h3>
            <div className="stat-group">
              {m.category_breakdown && Object.entries(m.category_breakdown as Record<string, number>).map(([cat, count]) => (
                <div className="stat" key={cat}>
                  <span className="stat-value">{count}</span>
                  <span className="stat-label">{cat.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
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
                  <span className="stat-label">{status.charAt(0).toUpperCase() + status.slice(1)}</span>
                </div>
              ))}
            </div>
          </article>

          {m.country_breakdown && Object.keys(m.country_breakdown).length > 0 && (
            <article className="panel">
              <h3>Country Breakdown</h3>
              <div className="stat-group">
                {Object.entries(m.country_breakdown as Record<string, number>).map(([country, count]) => (
                  <div className="stat" key={country}>
                    <span className="stat-value">{count}</span>
                    <span className="stat-label">{country}</span>
                  </div>
                ))}
              </div>
            </article>
          )}

          {m.average_satisfaction_index !== undefined && (
            <article className="panel">
              <h3>Customer Satisfaction</h3>
              <div className="stat-group">
                <div className="stat"><span className="stat-value">{m.average_satisfaction_index.toFixed(2)}</span><span className="stat-label">Avg Satisfaction (1–5)</span></div>
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
                    const idField = rec.incident_id || 'N/A';
                    return (
                      <article className="candidate-card" key={rec.row_number}>
                        <p><strong>Row {rec.row_number}</strong> · ID: {idField}</p>
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

      {historyLoading && <p className="message loading" role="status">Loading analysis history...</p>}
      {historyError && (
        <div className="message error" role="alert">
          <p>{historyError}</p>
          <button className="secondary" type="button" onClick={loadHistory}>Retry</button>
        </div>
      )}
      {!historyLoading && !historyError && history.length === 0 && (
        <p className="message">No saved analyses are available yet.</p>
      )}
      {history.length > 0 && (
        <section className="panel" style={{ marginTop: '1rem' }}>
          <h2>Previous Analyses</h2>
          <div className="detail-grid">
            {selectedHistoryLoading && <p className="message loading" role="status">Loading selected analysis…</p>}
            {history.map((item) => (
              <button
                key={item.id}
                className={`candidate-card ${selectedHistoryId === item.id ? 'selected' : ''}`}
                onClick={() => handleLoadFromHistory(item.id)}
                disabled={selectedHistoryLoading}
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