'use client';

import React, { useState, useCallback } from 'react';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface Period {
  from: string;
  to: string;
}

interface MetricItem {
  day?: string;
  event_type?: string;
  count: number;
  total?: number;
  failed?: number;
  rate?: number;
}

interface ReportMetrics {
  events_per_day: MetricItem[];
  error_rate_by_type: MetricItem[];
  event_type_distribution: MetricItem[];
  auth_failure_rate: MetricItem[];
}

interface TelemetryReport {
  period: Period;
  metrics: ReportMetrics;
}

/* ------------------------------------------------------------------ */
/*  Helper: format a date string                                       */
/* ------------------------------------------------------------------ */

function fmtDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return iso;
  }
}

/* ------------------------------------------------------------------ */
/*  Bar chart row                                                      */
/* ------------------------------------------------------------------ */

function BarChartRow({ item, valueKey, maxPx }: {
  item: MetricItem;
  valueKey: 'count' | 'rate';
  maxPx: number;
}) {
  const val = valueKey === 'rate' ? (item.rate ?? 0) : item.count;
  const maxVal = valueKey === 'rate' ? 1.0 : Math.max(item.count, 1);
  const pct = Math.max((val / maxVal) * 100, 2);
  const label = item.day ?? item.event_type ?? '—';
  const displayVal = valueKey === 'rate'
    ? `${(item.rate ?? 0 * 100).toFixed(1)}%`
    : String(item.count);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '3px' }}>
      <span style={{ minWidth: '100px', fontSize: '0.75rem', color: '#555' }}>{label}</span>
      <span
        style={{
          display: 'inline-block',
          height: '14px',
          background: 'var(--track-blue, #2563eb)',
          borderRadius: '3px',
          width: `${Math.max(pct * maxPx / 100, 2)}px`,
        }}
        title={String(val)}
      />
      <span style={{ fontSize: '0.75rem', fontWeight: 600, marginLeft: '4px' }}>{displayVal}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Inline helper components                                           */
/* ------------------------------------------------------------------ */

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card" style={{ marginBottom: '1rem' }}>
      <h3>{title}</h3>
      {children}
    </div>
  );
}

function SimpleTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
        <thead>
          <tr>
            {headers.map((h) => (
              <th key={h} style={{ textAlign: 'left', padding: '4px 8px', borderBottom: '1px solid #ddd' }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {row.map((cell, ci) => (
                <td key={ci} style={{ padding: '4px 8px', borderBottom: '1px solid #eee' }}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                     */
/* ------------------------------------------------------------------ */

export default function TelemetryReportPage() {
  const [report, setReport] = useState<TelemetryReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = useCallback(
    async (start?: string, end?: string) => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        if (start) params.set('start_date', start);
        if (end) params.set('end_date', end);
        const qs = params.toString();
        const url = '/api/telemetry/report' + (qs ? '?' + qs : '');
        const res = await fetch(url);
        if (!res.ok) {
          const text = await res.text().catch(() => 'Unknown error');
          throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
        }
        const data: TelemetryReport = await res.json();
        setReport(data);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to load telemetry report.');
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  React.useEffect(() => {
    fetchReport();
  }, []);

  /* ---- loading / error ---- */

  if (loading) {
    return <p className="message loading" role="status">Loading telemetry report…</p>;
  }

  if (error) {
    return (
      <div className="card error" style={{ borderLeft: '4px solid #e53e3e', padding: '0.75rem 1rem' }}>
        <p>{error}</p>
      </div>
    );
  }

  if (!report) {
    return <p className="message">No report loaded yet.</p>;
  }

  /* ---- data ---- */

  const m = report.metrics;

  return (
    <div>
      <div style={{ marginBottom: '1rem' }}>
        <h2>Telemetry Report</h2>
        <p style={{ color: '#666', fontSize: '0.875rem' }}>
          Period: {fmtDate(report.period.from)} — {fmtDate(report.period.to)}
        </p>
      </div>

      {/* Events per day — bar chart */}
      <Card title="Events per Day">
        {m.events_per_day.length === 0
          ? <p className="message">No data for this period.</p>
          : m.events_per_day.map((item) => (
              <BarChartRow key={item.day ?? 'evt'} item={item} valueKey="count" maxPx={60} />
            ))
        }
      </Card>

      {/* Error rate by type — table */}
      <Card title="Error Rate by Type">
        {m.error_rate_by_type.length === 0
          ? <p className="message">No data for this period.</p>
          : <SimpleTable
              headers={['Event Type', 'Count']}
              rows={m.error_rate_by_type.map((item) => [item.event_type ?? '—', String(item.count)])}
            />
        }
      </Card>

      {/* Event type distribution — table */}
      <Card title="Event Type Distribution">
        {m.event_type_distribution.length === 0
          ? <p className="message">No data for this period.</p>
          : <SimpleTable
              headers={['Event Type', 'Count']}
              rows={m.event_type_distribution.map((item) => [item.event_type ?? '—', String(item.count)])}
            />
        }
      </Card>

      {/* Auth failure rate — bar chart */}
      <Card title="Auth Failure Rate (daily)">
        {m.auth_failure_rate.length === 0
          ? <p className="message">No data for this period.</p>
          : m.auth_failure_rate.map((item) => (
              <BarChartRow key={item.day ?? 'auth'} item={item} valueKey="rate" maxPx={60} />
            ))
        }
      </Card>

      {/* Auth failure details table */}
      {m.auth_failure_rate.length > 0 && (
        <Card title="Auth Failure Details">
          <SimpleTable
            headers={['Day', 'Total', 'Failed', 'Rate']}
            rows={m.auth_failure_rate.map((item) => [
              item.day ?? '—',
              String(item.total ?? 0),
              String(item.failed ?? 0),
              item.rate !== undefined ? `${(item.rate * 100).toFixed(1)}%` : '—',
            ])}
          />
        </Card>
      )}
    </div>
  );
}