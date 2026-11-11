"""Pure KPI computation functions for the TrackFlow business performance pipeline.

These functions are stateless and testable — they transform a DataFrame of raw
telemetry events into the KPI values defined in the BRIEFING.

Every function takes a ``pd.DataFrame`` with at minimum columns
``event_type, warehouse, client_id, week_start`` and returns either a scalar
value or a filtered/aggregated DataFrame.

Usage::

    from data.process.kpi_functions import compute_inbound_volume, aggregate_weekly_kpis
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd


# ── required column constants ────────────────────────────────────────────────

REQUIRED_COLUMNS = {"warehouse", "client_id", "week_start", "event_type"}
GROUP_COLS = ["warehouse", "client_id", "week_start"]


# ── helpers ──────────────────────────────────────────────────────────────────

def _validate_columns(df: pd.DataFrame, extra: set[str] | None = None) -> None:
    """Raise ``ValueError`` if *df* is missing required columns."""
    needed = REQUIRED_COLUMNS | (extra or set())
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(
            f"DataFrame missing required columns: {missing}. "
            f"Got: {list(df.columns)}"
        )


def _validate_not_null(df: pd.DataFrame, column: str) -> None:
    """Raise ``ValueError`` if *column* in *df* contains any null values."""
    if df[column].isnull().any():
        bad = df[df[column].isnull()]
        raise ValueError(
            f"Column '{column}' contains {len(bad)} null value(s). "
            f"Null rows: {bad.to_dict(orient='records')}"
        )


# ── individual KPI functions ─────────────────────────────────────────────────

def compute_inbound_volume(events: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame of *inbound_units_count* per (warehouse, client, week).

    Sums ``quantity`` from ``inbound_order_created`` events.
    """
    _validate_columns(events, {"quantity"})
    events["quantity"] = pd.to_numeric(events["quantity"], errors="coerce").fillna(0).astype(int)
    subset = events[events["event_type"] == "inbound_order_created"]
    if subset.empty:
        return pd.DataFrame(columns=GROUP_COLS + ["inbound_units_count"])
    return (
        subset.groupby(GROUP_COLS, as_index=False)["quantity"]
        .sum()
        .rename(columns={"quantity": "inbound_units_count"})
    )


def compute_outbound_throughput(events: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame of *outbound_orders_count* per (warehouse, client, week).

    Counts ``outbound_order_created`` events.
    """
    _validate_columns(events)
    subset = events[events["event_type"] == "outbound_order_created"]
    if subset.empty:
        return pd.DataFrame(columns=GROUP_COLS + ["outbound_orders_count"])
    return (
        subset.groupby(GROUP_COLS, as_index=False)
        .size()
        .rename(columns={"size": "outbound_orders_count"})
    )


def compute_stockout_frequency(events: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame of *stockout_events_count* per (warehouse, client, week).

    Counts ``stock_threshold_triggered`` events.
    """
    _validate_columns(events)
    subset = events[events["event_type"] == "stock_threshold_triggered"]
    if subset.empty:
        return pd.DataFrame(columns=GROUP_COLS + ["stockout_events_count"])
    return (
        subset.groupby(GROUP_COLS, as_index=False)
        .size()
        .rename(columns={"size": "stockout_events_count"})
    )


def compute_discrepancy_frequency(events: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame of *discrepancy_events_count* per (warehouse, client, week).

    Counts ``inventory_discrepancy_detected`` events.
    """
    _validate_columns(events)
    subset = events[events["event_type"] == "inventory_discrepancy_detected"]
    if subset.empty:
        return pd.DataFrame(columns=GROUP_COLS + ["discrepancy_events_count"])
    return (
        subset.groupby(GROUP_COLS, as_index=False)
        .size()
        .rename(columns={"size": "discrepancy_events_count"})
    )


# ── aggregation orchestrator ─────────────────────────────────────────────────

def compute_discrepancy_rate(
    discrepancy_count: pd.DataFrame, outbound_count: pd.DataFrame
) -> pd.DataFrame:
    """Merge discrepancy and outbound counts and compute the rate.

    The rate is ``discrepancy_events_count / outbound_orders_count``,
    clamped to 0 when outbound_orders_count is 0.

    Returns a DataFrame with columns ``GROUP_COLS + ["discrepancy_rate"]``.
    """
    if outbound_count.empty:
        merged = discrepancy_count.copy()
        merged["outbound_orders_count"] = 0
        merged["discrepancy_rate"] = 0.0
        return merged[GROUP_COLS + ["discrepancy_rate", "discrepancy_events_count", "outbound_orders_count"]]

    merged = discrepancy_count.merge(
        outbound_count, on=GROUP_COLS, how="outer"
    ).fillna(0)
    merged["discrepancy_rate"] = (
        merged["discrepancy_events_count"] / merged["outbound_orders_count"]
    ).fillna(0.0).round(4)
    return merged[GROUP_COLS + ["discrepancy_rate", "discrepancy_events_count", "outbound_orders_count"]]


def aggregate_weekly_kpis(events: pd.DataFrame) -> pd.DataFrame:
    """Orchestrate all KPI computations into a single KPI DataFrame.

    This is the full pipeline transformation — it calls each individual
    KPI function and merges the results into the output format expected
    by ``reporting.weekly_warehouse_client_performance``.

    Parameters
    ----------
    events : pd.DataFrame
        Raw telemetry events with columns
        ``event_type, warehouse, client_id, week_start, quantity``.

    Returns
    -------
    pd.DataFrame
        KPI rows with columns matching the destination table.
    """
    _validate_columns(events, {"quantity"})

    inbound = compute_inbound_volume(events)
    outbound = compute_outbound_throughput(events)
    stockout = compute_stockout_frequency(events)
    discrepancy = compute_discrepancy_frequency(events)

    # Merge all on group cols — outer merge preserves combinations
    # that have zero events of a given type.
    result = inbound.merge(outbound, on=GROUP_COLS, how="outer")
    result = result.merge(stockout, on=GROUP_COLS, how="outer")
    result = result.merge(discrepancy, on=GROUP_COLS, how="outer")

    # Fill NaN with 0 for count columns
    numeric_cols = [
        "inbound_units_count",
        "outbound_orders_count",
        "stockout_events_count",
        "discrepancy_events_count",
    ]
    for col in numeric_cols:
        result[col] = pd.to_numeric(result.get(col, 0).fillna(0), errors="coerce").fillna(0).astype(int)

    # Discrepancy rate (0 if no outbound orders)
    result["discrepancy_rate"] = result.apply(
        lambda r: round(
            r["discrepancy_events_count"] / r["outbound_orders_count"], 4
        ) if r["outbound_orders_count"] > 0 else 0.0,
        axis=1,
    )

    result["computed_at"] = datetime.now(timezone.utc)

    return result