"use client";

import React, { useCallback, useEffect, useState } from "react";
import { fetchJson, userSafeErrorMessage } from "../../src/utils/api-errors";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface PerformanceEntry {
  warehouse: string;
  client_id: string;
  inbound_units_count: number;
  outbound_orders_count: number;
  stockout_events_count: number;
  discrepancy_events_count: number;
  discrepancy_rate: number;
}

interface PerformanceResponse {
  week_start: string;
  computed_at: string;
  entries: PerformanceEntry[];
}

interface WatermarkResponse {
  pipeline_name: string;
  last_completed_week: string;
  last_run_at: string;
  status: string;
  started_at?: string;
  completed_at?: string;
  rows_extracted?: number;
  rows_upserted?: number;
  error_message?: string | null;
}

interface TriggerResponse {
  week_start: string;
  status: string;
  rows_upserted: number;
  error?: string;
}

/* ------------------------------------------------------------------ */
/*  Helper: format ISO date                                            */
/* ------------------------------------------------------------------ */

function fmtDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

/* ------------------------------------------------------------------ */
/*  KPI Card                                                           */
/* ------------------------------------------------------------------ */

function KpiCard({
  label,
  value,
  unit,
  color,
}: {
  label: string;
  value: string | number;
  unit?: string;
  color: string;
}) {
  return (
    <div
      className="card"
      style={{
        borderLeft: `4px solid ${color}`,
        minWidth: "160px",
        flex: "1 1 160px",
      }}
    >
      <p style={{ fontSize: "0.75rem", color: "#666", margin: "0 0 4px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {label}
      </p>
      <p style={{ fontSize: "1.5rem", fontWeight: 700, margin: 0 }}>
        {value}
        {unit && <span style={{ fontSize: "0.875rem", fontWeight: 400, color: "#888", marginLeft: "4px" }}>{unit}</span>}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function WeeklyReportingDashboard() {
  const [weekStart, setWeekStart] = useState<string>("");
  const [data, setData] = useState<PerformanceResponse | null>(null);
  const [watermark, setWatermark] = useState<WatermarkResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<TriggerResponse | null>(null);

  /* Fetch performance data and watermark */
  const fetchData = useCallback(async (week?: string) => {
    setLoading(true);
    setError("");
    setTriggerResult(null);

    try {
      const params = week ? `?week_start=${week}` : "";
      const [perfRes, wmRes] = await Promise.all([
        fetchJson<PerformanceResponse>(`/api/reporting/weekly-warehouse-client-performance${params}`),
        fetchJson<WatermarkResponse>("/api/reporting/pipeline-runs/latest"),
      ]);
      setData(perfRes);
      setWatermark(wmRes);
      setWeekStart(perfRes.week_start);
    } catch (err: unknown) {
      setError(userSafeErrorMessage(err, "Could not load reporting data."));
    } finally {
      setLoading(false);
    }
  }, []);

  /* Trigger a new pipeline run */
  const triggerPipeline = useCallback(async () => {
    setTriggering(true);
    setTriggerResult(null);
    setError("");

    try {
      const body = weekStart ? { week_start: weekStart } : {};
      const res = await fetchJson<TriggerResponse>("/api/reporting/pipeline-runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setTriggerResult(res);
      // Refresh data after trigger
      await fetchData(res.week_start);
    } catch (err: unknown) {
      setError(userSafeErrorMessage(err, "Could not trigger pipeline run."));
    } finally {
      setTriggering(false);
    }
  }, [weekStart, fetchData]);

  /* Initial fetch on mount */
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  /* ── Aggregate summary across all entries ── */
  const summary = React.useMemo(() => {
    if (!data || data.entries.length === 0) return null;
    const totalInbound = data.entries.reduce((s, e) => s + e.inbound_units_count, 0);
    const totalOutbound = data.entries.reduce((s, e) => s + e.outbound_orders_count, 0);
    const totalStockouts = data.entries.reduce((s, e) => s + e.stockout_events_count, 0);
    const totalDiscrepancies = data.entries.reduce((s, e) => s + e.discrepancy_events_count, 0);
    const avgRate =
      totalOutbound > 0
        ? (totalDiscrepancies / totalOutbound)
        : 0;

    return {
      totalInbound,
      totalOutbound,
      totalStockouts,
      totalDiscrepancies,
      avgRate,
      entryCount: data.entries.length,
    };
  }, [data]);

  return (
    <section>
      <header className="page-header">
        <span className="badge green">TrackFlow performance reports</span>
        <h1>Weekly Warehouse × Client KPIs</h1>
        <p>
          Aggregate performance metrics computed by the ETL pipeline from telemetry events,
          grouped by warehouse and client per ISO week.
        </p>
        <div className="actions" style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <input
            type="date"
            value={weekStart}
            onChange={(e) => setWeekStart(e.target.value)}
            style={{ padding: "6px 10px", borderRadius: "4px", border: "1px solid #ccc" }}
            title="Select ISO week start (Monday)"
          />
          <button
            className="button"
            onClick={() => fetchData(weekStart)}
            disabled={loading}
          >
            {loading ? "Loading…" : "Query"}
          </button>
          <button
            className="button secondary"
            onClick={triggerPipeline}
            disabled={triggering}
          >
            {triggering ? "Running…" : "Run Pipeline Now"}
          </button>
        </div>
      </header>

      {/* ── Error ── */}
      {error && (
        <div className="panel" style={{ background: "#fff0f0", border: "1px solid #fcc", padding: "12px", marginBottom: "1rem" }}>
          <p style={{ color: "#c00", margin: 0 }}>{error}</p>
        </div>
      )}

      {/* ── Trigger result ── */}
      {triggerResult && (
        <div
          className="panel"
          style={{
            background: triggerResult.status === "success" ? "#f0fff0" : "#fff8f0",
            border: `1px solid ${triggerResult.status === "success" ? "#cfc" : "#fdb"}`,
            padding: "12px",
            marginBottom: "1rem",
          }}
        >
          <p style={{ margin: 0 }}>
            <strong>Pipeline {triggerResult.status}:</strong> week {triggerResult.week_start}
            {triggerResult.rows_upserted > 0 && ` — ${triggerResult.rows_upserted} rows upserted`}
            {triggerResult.error && <span style={{ color: "#c00" }}> — {triggerResult.error}</span>}
          </p>
        </div>
      )}

      {/* ── Watermark ── */}
      {watermark && (
        <div className="panel" style={{ padding: "12px", marginBottom: "1rem", fontSize: "0.875rem", color: "#555" }}>
          <strong>Last pipeline run:</strong>{" "}
          {fmtDate(watermark.last_run_at)} — week {watermark.last_completed_week}
          {watermark.rows_upserted !== undefined && (
            <> &middot; {watermark.rows_extracted ?? "?"} events &rarr; {watermark.rows_upserted} rows</>
          )}
          {watermark.error_message && (
            <span style={{ color: "#c00", marginLeft: "8px" }}>Error: {watermark.error_message}</span>
          )}
        </div>
      )}

      {/* ── Loading ── */}
      {loading && (
        <p className="message loading">Loading performance data…</p>
      )}

      {/* ── Summary KPI cards ── */}
      {summary && !loading && (
        <div
          className="panel"
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "12px",
            marginBottom: "1rem",
          }}
        >
          <KpiCard label="Inbound Volume" value={summary.totalInbound} unit="units" color="#2563eb" />
          <KpiCard label="Outbound Throughput" value={summary.totalOutbound} unit="orders" color="#16a34a" />
          <KpiCard label="Stockout Frequency" value={summary.totalStockouts} unit="events" color="#dc2626" />
          <KpiCard label="Discrepancy Events" value={summary.totalDiscrepancies} unit="events" color="#f59e0b" />
          <KpiCard label="Discrepancy Rate" value={(summary.avgRate * 100).toFixed(2)} unit="%" color="#8b5cf6" />
          <KpiCard label="Warehouse × Client Combos" value={summary.entryCount} unit="rows" color="#06b6d4" />
        </div>
      )}

      {/* ── Detail table ── */}
      {data && !loading && data.entries.length > 0 && (
        <div className="panel">
          <h3 style={{ marginTop: 0 }}>
            KPIs for week starting {fmtDate(data.week_start)}
          </h3>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", padding: "6px 10px", borderBottom: "2px solid #ddd" }}>Warehouse</th>
                  <th style={{ textAlign: "left", padding: "6px 10px", borderBottom: "2px solid #ddd" }}>Client</th>
                  <th style={{ textAlign: "right", padding: "6px 10px", borderBottom: "2px solid #ddd" }}>Inbound Volume</th>
                  <th style={{ textAlign: "right", padding: "6px 10px", borderBottom: "2px solid #ddd" }}>Outbound Throughput</th>
                  <th style={{ textAlign: "right", padding: "6px 10px", borderBottom: "2px solid #ddd" }}>Stockout Frequency</th>
                  <th style={{ textAlign: "right", padding: "6px 10px", borderBottom: "2px solid #ddd" }}>Discrepancy Count</th>
                  <th style={{ textAlign: "right", padding: "6px 10px", borderBottom: "2px solid #ddd" }}>Discrepancy Rate</th>
                </tr>
              </thead>
              <tbody>
                {data.entries.map((e, i) => (
                  <tr key={`${e.warehouse}-${e.client_id}-${i}`}>
                    <td style={{ padding: "4px 10px", borderBottom: "1px solid #eee", fontWeight: 500 }}>
                      {e.warehouse}
                    </td>
                    <td style={{ padding: "4px 10px", borderBottom: "1px solid #eee" }}>
                      {e.client_id}
                    </td>
                    <td style={{ padding: "4px 10px", borderBottom: "1px solid #eee", textAlign: "right" }}>
                      {e.inbound_units_count.toLocaleString()}
                    </td>
                    <td style={{ padding: "4px 10px", borderBottom: "1px solid #eee", textAlign: "right" }}>
                      {e.outbound_orders_count.toLocaleString()}
                    </td>
                    <td style={{ padding: "4px 10px", borderBottom: "1px solid #eee", textAlign: "right" }}>
                      {e.stockout_events_count.toLocaleString()}
                    </td>
                    <td style={{ padding: "4px 10px", borderBottom: "1px solid #eee", textAlign: "right" }}>
                      {e.discrepancy_events_count.toLocaleString()}
                    </td>
                    <td style={{ padding: "4px 10px", borderBottom: "1px solid #eee", textAlign: "right" }}>
                      <span
                        style={{
                          color: e.discrepancy_rate > 0.05 ? "#dc2626" : e.discrepancy_rate > 0.02 ? "#f59e0b" : "#16a34a",
                          fontWeight: 600,
                        }}
                      >
                        {(e.discrepancy_rate * 100).toFixed(2)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Empty state ── */}
      {data && !loading && data.entries.length === 0 && (
        <div className="panel" style={{ textAlign: "center", padding: "2rem" }}>
          <p style={{ color: "#888" }}>
            No KPI data found for week {weekStart || "selected"}. Run the pipeline first.
          </p>
        </div>
      )}
    </section>
  );
}