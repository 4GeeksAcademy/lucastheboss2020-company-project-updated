"""TrackFlow business performance pipeline.

Implements the weekly warehouse × client KPI pipeline described in
``data/pipelines/PIPELINE_DESIGN.md``.

Exported symbols (imported by ``services/reporting/router.py``):
    - ``compute_weekly_kpis(week_start)`` — run transform only over stored data
    - ``get_latest_watermark()`` — return the latest pipeline watermark row
    - ``run_pipeline(week_start)`` — trigger a full pipeline run synchronously

Entry point (CLI)::

    python data/pipelines/pipeline.py 2026-07-13
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import psycopg2
from prefect import flow, task
from psycopg2.extras import execute_values

from services.telemetry_storage import _connect, _get_dsn, _dsn_is_postgres

logger = logging.getLogger(__name__)

# ── module-level DDL guard ───────────────────────────────────────────────────

_SCHEMA_DDL = """
CREATE SCHEMA IF NOT EXISTS reporting;

CREATE TABLE IF NOT EXISTS reporting.weekly_warehouse_client_performance (
  id uuid primary key default gen_random_uuid(),
  warehouse text not null,
  client_id text not null,
  week_start date not null,
  inbound_units_count integer not null default 0,
  outbound_orders_count integer not null default 0,
  stockout_events_count integer not null default 0,
  discrepancy_events_count integer not null default 0,
  discrepancy_rate numeric not null default 0,
  computed_at timestamptz not null default now(),
  unique (warehouse, client_id, week_start)
);

CREATE INDEX IF NOT EXISTS idx_weekly_perf_week_start
  ON reporting.weekly_warehouse_client_performance (week_start DESC);

CREATE TABLE IF NOT EXISTS reporting.pipeline_watermark (
  pipeline_name text primary key,
  last_completed_week date not null,
  last_run_at timestamptz not null default now(),
  status text not null default 'success'
);

CREATE TABLE IF NOT EXISTS reporting.pipeline_run_log (
  run_id uuid primary key default gen_random_uuid(),
  pipeline_name text not null,
  week_start date not null,
  status text not null default 'running',
  rows_extracted integer not null default 0,
  rows_upserted integer not null default 0,
  error_message text,
  started_at timestamptz not null default now(),
  completed_at timestamptz
);
"""


def _ensure_reporting_schema() -> None:
    """Create the ``reporting`` schema and all pipeline tables if they do not exist.

    Safe to call on every run — uses IF NOT EXISTS.
    """
    dsn = _get_dsn()
    if not dsn or not _dsn_is_postgres(dsn):
        logger.info("No PostgreSQL DSN — skipping schema creation")
        return
    conn = psycopg2.connect(dsn, connect_timeout=5)
    try:
        with conn.cursor() as cur:
            for statement in _SCHEMA_DDL.split(";"):
                cleaned = statement.strip()
                if cleaned:
                    cur.execute(cleaned)
        conn.commit()
        logger.info("Reporting schema and tables ensured")
    finally:
        conn.close()


# ── date helpers ─────────────────────────────────────────────────────────────

def _week_bounds(week_start: str) -> tuple[str, str]:
    """Return ``(start, end)`` ISO-format timestamps for the given ISO week Monday.

    The window covers ``[week_start 00:00:00, week_start + 7 days 00:00:00)``.
    """
    from pandas import Timestamp
    s = Timestamp(week_start).tz_localize("UTC")
    e = s + pd.Timedelta(days=7)
    return s.isoformat(), e.isoformat()


# ── tasks ────────────────────────────────────────────────────────────────────

@task(
    tags=["service:reporting", "task:extract"],
    retries=2,
    retry_delay_seconds=30,
    # Reason for 2 retries: database connections can transiently fail (pool
    # exhaustion, brief network flap).  Two retries at 30 s apart absorb
    # almost all intermittent issues without masking a real outage.
    cache_key_fn=lambda ctx, inputs: str(inputs.get("week_start", "")),
    cache_expiration=timedelta(seconds=3600),
    # Cache key = the ISO week string.  Past weeks' telemetry_events are
    # append-only, so the extracted data is stable.  3600 s (1 h) means a
    # re-run within the same hour reuses the cached extraction without
    # hitting the database again.
)
def extract_events(week_start: str) -> pd.DataFrame:
    """Extract raw inventory events for the given ISO week from ``telemetry_events``.

    Returns a DataFrame with columns:
        warehouse, client_id, week_start, event_type, quantity
    """
    start_iso, end_iso = _week_bounds(week_start)

    query = """
        SELECT
          tags->>'warehouse'                          AS warehouse,
          tags->>'client_id'                          AS client_id,
          DATE_TRUNC('week', timestamp::date)::date   AS week_start,
          event_type,
          COALESCE((tags->>'quantity')::integer, 0)   AS quantity
        FROM telemetry_events
        WHERE event_type IN (
              'inbound_order_created',
              'outbound_order_created',
              'stock_threshold_triggered',
              'inventory_discrepancy_detected'
          )
          AND timestamp >= %(start)s
          AND timestamp <  %(end)s
    """
    dsn = _get_dsn()
    if not dsn or not _dsn_is_postgres(dsn):
        logger.warning("No PostgreSQL DSN configured — returning empty extraction")
        return pd.DataFrame(columns=["warehouse", "client_id", "week_start", "event_type", "quantity"])

    conn = _connect()
    try:
        df = pd.read_sql(query, conn, params={"start": start_iso, "end": end_iso})
        logger.info("Extracted %d events for week %s", len(df), week_start)
        return df
    finally:
        conn.close()


@task(
    tags=["service:reporting", "task:transform"],
    cache_key_fn=lambda ctx, inputs: str(inputs.get("raw_df", id(inputs.get("raw_df", "")))),
    cache_expiration=timedelta(seconds=3600),
)
def transform_to_kpis(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate raw events into warehouse × client × week KPI rows.

    Fully vectorised — no Python loops over DataFrame rows.

    Output columns match ``reporting.weekly_warehouse_client_performance``
    (excluding ``id`` and ``computed_at``).
    """
    required = {"warehouse", "client_id", "week_start", "event_type", "quantity"}
    missing = required - set(raw_df.columns)
    if missing:
        raise ValueError(
            f"Input DataFrame missing required columns: {missing}. "
            f"Got columns: {list(raw_df.columns)}"
        )

    # Build 4 filtered views — each grouped by [warehouse, client_id, week_start]
    group_cols = ["warehouse", "client_id", "week_start"]

    inbound = (
        raw_df[raw_df["event_type"] == "inbound_order_created"]
        .groupby(group_cols, as_index=False)["quantity"]
        .sum()
        .rename(columns={"quantity": "inbound_units_count"})
    )

    outbound = (
        raw_df[raw_df["event_type"] == "outbound_order_created"]
        .groupby(group_cols, as_index=False)
        .size()
        .rename(columns={"size": "outbound_orders_count"})
    )

    stockout = (
        raw_df[raw_df["event_type"] == "stock_threshold_triggered"]
        .groupby(group_cols, as_index=False)
        .size()
        .rename(columns={"size": "stockout_events_count"})
    )

    discrepancy = (
        raw_df[raw_df["event_type"] == "inventory_discrepancy_detected"]
        .groupby(group_cols, as_index=False)
        .size()
        .rename(columns={"size": "discrepancy_events_count"})
    )

    # Merge all four on group cols — outer merge preserves warehouse-client
    # combinations that have zero events of a given type.
    result = inbound.merge(outbound, on=group_cols, how="outer")
    result = result.merge(stockout, on=group_cols, how="outer")
    result = result.merge(discrepancy, on=group_cols, how="outer")

    # Fill NaN with 0 — a warehouse-client may have 0 stockouts (= 0 rows in
    # that filtered view), which becomes NaN after outer merge.
    numeric_cols = [
        "inbound_units_count",
        "outbound_orders_count",
        "stockout_events_count",
        "discrepancy_events_count",
    ]
    for col in numeric_cols:
        result[col] = result.get(col, 0).fillna(0).astype(int)

    # Compute discrepancy rate
    result["discrepancy_rate"] = (
        result["discrepancy_events_count"] / result["outbound_orders_count"]
    ).fillna(0.0).round(4)

    result["computed_at"] = datetime.now(timezone.utc)

    logger.info(
        "Transformed into %d KPI rows for %d warehouse-client combinations",
        len(result),
        result.groupby(["warehouse", "client_id"]).ngroups,
    )
    return result


@task(
    tags=["service:reporting", "task:load"],
    retries=2,
    retry_delay_seconds=30,
    # Reason for 2 retries: upsert can hit serialisation/deadlock under
    # concurrent writes.  Two retries resolve most contention without
    # indefinite blocking.
)
def load_to_reporting(kpi_df: pd.DataFrame) -> int:
    """Upsert KPI rows into ``reporting.weekly_warehouse_client_performance``.

    Idempotent: ``ON CONFLICT (warehouse, client_id, week_start) DO UPDATE``
    ensures re-running the same week produces identical data.

    Returns the number of rows upserted.
    """
    if kpi_df.empty:
        logger.info("No KPI rows to load — skipping upsert")
        return 0

    dsn = _get_dsn()
    if not dsn or not _dsn_is_postgres(dsn):
        logger.warning("No PostgreSQL DSN configured — cannot load KPI data")
        return 0

    conn = psycopg2.connect(dsn, connect_timeout=5)
    try:
        rows = [
            (
                row["warehouse"],
                row["client_id"],
                row["week_start"],
                int(row["inbound_units_count"]),
                int(row["outbound_orders_count"]),
                int(row["stockout_events_count"]),
                int(row["discrepancy_events_count"]),
                float(row["discrepancy_rate"]),
                row["computed_at"],
            )
            for _, row in kpi_df.iterrows()
        ]

        upsert_sql = """
            INSERT INTO reporting.weekly_warehouse_client_performance
                (warehouse, client_id, week_start, inbound_units_count,
                 outbound_orders_count, stockout_events_count,
                 discrepancy_events_count, discrepancy_rate, computed_at)
            VALUES %s
            ON CONFLICT (warehouse, client_id, week_start)
            DO UPDATE SET
                inbound_units_count       = EXCLUDED.inbound_units_count,
                outbound_orders_count     = EXCLUDED.outbound_orders_count,
                stockout_events_count     = EXCLUDED.stockout_events_count,
                discrepancy_events_count  = EXCLUDED.discrepancy_events_count,
                discrepancy_rate          = EXCLUDED.discrepancy_rate,
                computed_at               = EXCLUDED.computed_at
        """
        with conn.cursor() as cur:
            execute_values(cur, upsert_sql, rows, template=None)
        conn.commit()
        logger.info("Upserted %d KPI rows into reporting schema", len(rows))
        return len(rows)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@task(
    tags=["service:reporting", "task:watermark"],
    retries=1,
    retry_delay_seconds=10,
    # Watermark is advisory — 1 retry is enough to cover brief blips.
)
def record_watermark(week_start: str, status: str) -> None:
    """Update the pipeline watermark with the latest completed week.

    This task is **optional** — it is invoked with ``return_state=True`` so
    a failure here does not interrupt the main extract → transform → load flow.
    """
    dsn = _get_dsn()
    if not dsn or not _dsn_is_postgres(dsn):
        logger.warning("No PostgreSQL DSN — skipping watermark update")
        return

    conn = psycopg2.connect(dsn, connect_timeout=5)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO reporting.pipeline_watermark
                    (pipeline_name, last_completed_week, last_run_at, status)
                VALUES (%s, %s, NOW(), %s)
                ON CONFLICT (pipeline_name)
                DO UPDATE SET
                    last_completed_week = EXCLUDED.last_completed_week,
                    last_run_at = NOW(),
                    status = EXCLUDED.status
                """,
                ("weekly_client_performance", week_start, status),
            )
        conn.commit()
        logger.info("Watermark updated: week=%s status=%s", week_start, status)
    except Exception:
        conn.rollback()
        logger.warning("Watermark update failed (non-fatal): week=%s", week_start)
    finally:
        conn.close()


# ── stand-alone functions (imported by services/reporting/router.py) ─────────

def compute_weekly_kpis(week_start: str) -> list[dict[str, Any]]:
    """Return the computed KPI rows for a given week, directly from the DB.

    Queries ``reporting.weekly_warehouse_client_performance`` for the given
    week and returns the rows as a list of dicts matching the BRIEFING contract.

    This is the function imported by ``services/reporting/router.py`` for the
    ``GET /reporting/weekly-warehouse-client-performance`` endpoint.
    """
    dsn = _get_dsn()
    if not dsn or not _dsn_is_postgres(dsn):
        logger.warning("No PostgreSQL DSN — returning empty KPI list")
        return []

    conn = psycopg2.connect(dsn, connect_timeout=5)
    try:
        query = """
            SELECT
                warehouse,
                client_id,
                inbound_units_count,
                outbound_orders_count,
                stockout_events_count,
                discrepancy_events_count,
                discrepancy_rate
            FROM reporting.weekly_warehouse_client_performance
            WHERE week_start = %s
            ORDER BY warehouse, client_id
        """
        df = pd.read_sql(query, conn, params=[week_start])
        return df.to_dict(orient="records")
    finally:
        conn.close()


def get_latest_watermark() -> dict[str, Any]:
    """Return the latest pipeline run entry from the run log.

    This is the function imported by ``services/reporting/router.py`` for the
    ``GET /reporting/pipeline-runs/latest`` endpoint.
    Now returns the full pipeline_run_log record (started_at, completed_at,
    rows_extracted, rows_upserted) instead of just the watermark table.
    """
    dsn = _get_dsn()
    if not dsn or not _dsn_is_postgres(dsn):
        return {"pipeline_name": "weekly_client_performance", "status": "never_run"}

    conn = psycopg2.connect(dsn, connect_timeout=5)
    try:
        query = """
            SELECT pipeline_name, week_start, status, rows_extracted,
                   rows_upserted, error_message, started_at, completed_at
            FROM reporting.pipeline_run_log
            WHERE pipeline_name = 'weekly_client_performance'
            ORDER BY started_at DESC
            LIMIT 1
        """
        df = pd.read_sql(query, conn)
        if df.empty:
            return {
                "pipeline_name": "weekly_client_performance",
                "status": "never_run",
            }
        row = df.iloc[0]
        return {
            "pipeline_name": row["pipeline_name"],
            "last_completed_week": str(row["week_start"]),
            "last_run_at": row["started_at"].isoformat() if hasattr(row["started_at"], "isoformat") else str(row["started_at"]),
            "status": row["status"],
            "rows_extracted": int(row["rows_extracted"]),
            "rows_upserted": int(row["rows_upserted"]),
            "started_at": row["started_at"].isoformat() if hasattr(row["started_at"], "isoformat") else str(row["started_at"]),
            "completed_at": row["completed_at"].isoformat() if (hasattr(row.get("completed_at"), "isoformat")) else (str(row["completed_at"]) if row["completed_at"] else None),
            "error_message": row["error_message"],
        }
    finally:
        conn.close()


def run_pipeline(week_start: str) -> dict[str, Any]:
    """Trigger a full pipeline run synchronously.

    This is the function imported by ``services/reporting/router.py`` for the
    ``POST /reporting/pipeline-runs`` endpoint.
    """
    return weekly_client_performance_pipeline(week_start=week_start)


# ── flow ─────────────────────────────────────────────────────────────────────

@flow(
    name="weekly_client_performance",
    description="Compute weekly warehouse × client KPIs from telemetry events",
    # NOTE: Scheduling (e.g. cron="0 1 * * 1" for Mondays at 01:00 UTC)
    #       is configured via Prefect deployments, not the @flow decorator.
)
def weekly_client_performance_pipeline(week_start: str | None = None) -> dict[str, Any]:
    """Main pipeline: extract → transform → load → record watermark.

    Parameters
    ----------
    week_start : str, optional
        ISO date string for the Monday of the target week.
        Defaults to the most recent Monday (previous week).

    Returns
    -------
    dict with keys ``week_start``, ``rows_upserted``, ``status``.
    """
    # ── resolve week_start ──────────────────────────────────────────────
    if week_start is None:
        # Default to the most recent completed ISO week (previous Monday)
        today = datetime.now(timezone.utc)
        # Monday = 0 in Python weekday().  Go back to the most recent Monday.
        days_since_monday = today.weekday()
        last_monday = today - pd.Timedelta(days=days_since_monday + 7)
        week_start = last_monday.strftime("%Y-%m-%d")
        logger.info("No week_start given — defaulting to %s", week_start)

    # ── input validation ────────────────────────────────────────────────
    from datetime import datetime as dt
    try:
        parsed = dt.strptime(week_start, "%Y-%m-%d")
    except ValueError:
        return {"week_start": week_start, "status": "invalid_date", "rows_upserted": 0}

    if parsed.weekday() != 0:
        return {"week_start": week_start, "status": "not_a_monday", "rows_upserted": 0}

    now = dt.now()
    if parsed > now:
        return {"week_start": week_start, "status": "future_date", "rows_upserted": 0}

    if (now - parsed).days > 365:
        return {"week_start": week_start, "status": "too_far_in_past", "rows_upserted": 0}

    # ── ensure schema exists ────────────────────────────────────────────
    _ensure_reporting_schema()

    # ── run ID for audit log ────────────────────────────────────────────
    run_id = None
    dsn = _get_dsn()
    if dsn and _dsn_is_postgres(dsn):
        try:
            conn = psycopg2.connect(dsn, connect_timeout=5)
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO reporting.pipeline_run_log
                       (pipeline_name, week_start, status, started_at)
                       VALUES ('weekly_client_performance', %s, 'running', NOW())
                       RETURNING run_id""",
                    (week_start,),
                )
                run_id = cur.fetchone()[0]
            conn.commit()
            conn.close()
        except Exception:
            logger.warning("Could not write audit log start entry (non-fatal)")

    # ── pipeline stages ─────────────────────────────────────────────────
    start_time = time.perf_counter()
    status = "success"
    rows_upserted = 0
    rows_extracted = 0
    error_message: str | None = None

    try:
        # Extract
        raw_df = extract_events(week_start)
        rows_extracted = len(raw_df)
        logger.info("Stage 1 (extract): %d events in %.2f s", rows_extracted, time.perf_counter() - start_time)

        # Transform
        kpi_df = transform_to_kpis(raw_df)
        logger.info("Stage 2 (transform): %d rows in %.2f s", len(kpi_df), time.perf_counter() - start_time)

        # Load (critical — failure propagates)
        rows_upserted = load_to_reporting(kpi_df)
        logger.info("Stage 3 (load): %d rows upserted in %.2f s", rows_upserted, time.perf_counter() - start_time)

    except Exception as exc:
        status = "failed"
        error_message = str(exc)
        logger.error("Pipeline failed: %s", error_message)
        # Still attempt watermark update with failed status
        try:
            record_watermark(week_start, "failed")
        except Exception:
            logger.warning("Watermark update after failure also failed (non-fatal)")
        # Update audit log if we have a run_id
        if run_id:
            _update_run_log(run_id, "failed", rows_extracted, 0, error_message)
        return {
            "week_start": week_start,
            "status": "failed",
            "rows_upserted": 0,
            "error": error_message,
        }

    # ── record watermark (optional — failure does not fail the flow) ────
    watermark_future = record_watermark.submit(week_start, "success", return_state=True)
    watermark_state = watermark_future.result(raise_on_failure=False)
    watermark_ok = watermark_state.is_successful()
    if not watermark_ok:
        logger.warning("Watermark update failed (non-fatal): %s", watermark_state.message)

    total_time = time.perf_counter() - start_time
    logger.info(
        "Pipeline completed in %.2f s: %d events → %d rows upserted (watermark=%s)",
        total_time, rows_extracted, rows_upserted,
        "ok" if watermark_ok else "failed (ignored)",
    )

    # ── update audit log ────────────────────────────────────────────────
    if run_id:
        _update_run_log(run_id, "success", rows_extracted, rows_upserted, None)

    return {
        "week_start": week_start,
        "status": "success",
        "rows_upserted": rows_upserted,
    }


def _update_run_log(run_id: str, status: str, rows_extracted: int, rows_upserted: int, error_message: str | None) -> None:
    """Update the pipeline run audit log entry."""
    dsn = _get_dsn()
    if not dsn or not _dsn_is_postgres(dsn):
        return
    try:
        conn = psycopg2.connect(dsn, connect_timeout=5)
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE reporting.pipeline_run_log
                   SET status = %s,
                       rows_extracted = %s,
                       rows_upserted = %s,
                       error_message = %s,
                       completed_at = NOW()
                   WHERE run_id = %s""",
                (status, rows_extracted, rows_upserted, error_message, run_id),
            )
        conn.commit()
        conn.close()
    except Exception:
        logger.warning("Could not update audit log (non-fatal)")


# ── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    week_start = sys.argv[1] if len(sys.argv) > 1 else None
    result = weekly_client_performance_pipeline(week_start=week_start)
    print(f"\nPipeline result: {result}")
    sys.exit(0 if result.get("status") == "success" else 1)