"""Telemetry analysis pipeline — metric functions for the Technical Report.

Each function:
- Is **side-effect-free** (pure computation over database state).
- Accepts ``start_date`` / ``end_date`` (ISO-format strings or ``None``).
- Loads data from PostgreSQL via the same DSN/connection helpers as
  ``services.telemetry_storage``.
- Uses **Pandas groupby/agg** (no Python loops over rows).
- Converts timestamps via ``pandas.to_datetime()``.
- Returns a plain JSON-serialisable structure (``list[dict]``).

Functions
---------
- ``events_per_day(start_date, end_date)`` — event volume time series.
- ``error_rate_by_type(start_date, end_date)`` — count of ``api_error`` and
  ``frontend_error_uncaught`` events grouped by ``event_type``.
- ``event_type_distribution(start_date, end_date)`` — all event types by count.
- ``auth_failure_rate(start_date, end_date)`` — daily ratio of
  ``auth_login_failed / (auth_login_succeeded + auth_login_failed)``.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

# Reuse the same connection / DSN helpers as the storage layer.
from services.telemetry_storage import _connect

logger = logging.getLogger(__name__)

# ── helpers ───────────────────────────────────────────────────────────────────


def _fetch_data(query: str, params: tuple[Any, ...]) -> pd.DataFrame:
    """Execute *query* with *params* against PostgreSQL, return a DataFrame.

    Uses the same ``_connect()`` helper as the storage layer (reads
    ``TELEMETRY_DATABASE_URL`` or ``DATABASE_URL``).
    """
    conn = _connect()
    try:
        return pd.read_sql(query, conn, params=params)
    finally:
        conn.close()


def _ensure_dates(
    start_date: str | None,
    end_date: str | None,
) -> tuple[str, str]:
    """Fill in ``None`` boundaries: ``start_date`` defaults to 7 days ago,
    ``end_date`` defaults to *now* (both as ISO-format strings).

    The caller is responsible for converting to database-native types.
    """
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    if end_date is None:
        end_date = now.isoformat()
    if start_date is None:
        start_date = (now - timedelta(days=7)).isoformat()
    return start_date, end_date


# ── metric functions ──────────────────────────────────────────────────────────


def events_per_day(
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Event volume time series — count of events per calendar day.

    Returns::
        [{"day": "2024-01-01", "count": 142}, ...]
    """
    start_date, end_date = _ensure_dates(start_date, end_date)

    df = _fetch_data(
        """\
        SELECT timestamp, event_type
          FROM telemetry_events
         WHERE timestamp >= %s AND timestamp < %s
        """,
        (start_date, end_date),
    )

    if df.empty:
        return []

    df["day"] = pd.to_datetime(df["timestamp"], utc=True).dt.date
    grouped = df.groupby("day", as_index=False).agg(count=("event_type", "count"))
    grouped = grouped.sort_values("day")
    # Convert date → str for JSON serialisation
    grouped["day"] = grouped["day"].astype(str)
    return grouped.to_dict(orient="records")


def error_rate_by_type(
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Count of ``api_error`` and ``frontend_error_uncaught`` events by type.

    Returns::
        [{"event_type": "api_error", "count": 23}, ...]
    """
    start_date, end_date = _ensure_dates(start_date, end_date)

    df = _fetch_data(
        """\
        SELECT event_type
          FROM telemetry_events
         WHERE timestamp >= %s AND timestamp < %s
           AND event_type IN ('api_error', 'frontend_error_uncaught')
        """,
        (start_date, end_date),
    )

    if df.empty:
        return []

    grouped = df.groupby("event_type", as_index=False).agg(count=("event_type", "count"))
    grouped = grouped.sort_values("count", ascending=False)
    return grouped.to_dict(orient="records")


def event_type_distribution(
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Count of all event types in the period — highest first.

    Returns::
        [{"event_type": "inbound_order_created", "count": 87}, ...]
    """
    start_date, end_date = _ensure_dates(start_date, end_date)

    df = _fetch_data(
        """\
        SELECT event_type
          FROM telemetry_events
         WHERE timestamp >= %s AND timestamp < %s
        """,
        (start_date, end_date),
    )

    if df.empty:
        return []

    grouped = df.groupby("event_type", as_index=False).agg(count=("event_type", "count"))
    grouped = grouped.sort_values("count", ascending=False)
    return grouped.to_dict(orient="records")


def auth_failure_rate(
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Daily ratio of ``auth_login_failed / (auth_login_succeeded + auth_login_failed)``.

    Days with zero auth events are omitted.

    Returns::
        [
          {"day": "2024-01-01", "total": 58, "failed": 3, "rate": 0.0517},
          ...
        ]
    """
    start_date, end_date = _ensure_dates(start_date, end_date)

    df = _fetch_data(
        """\
        SELECT timestamp, event_type
          FROM telemetry_events
         WHERE timestamp >= %s AND timestamp < %s
           AND event_type IN ('auth_login_succeeded', 'auth_login_failed')
        """,
        (start_date, end_date),
    )

    if df.empty:
        return []

    df["day"] = pd.to_datetime(df["timestamp"], utc=True).dt.date

    # ── Group + pivot (no Python loops) ───────────────────────────────────
    pivot = df.groupby(["day", "event_type"], as_index=False).agg(count=("event_type", "count"))
    pivot = pivot.pivot_table(
        index="day",
        columns="event_type",
        values="count",
        fill_value=0,
    ).reset_index()

    # Ensure expected columns exist (both succeed + fail may not appear every day).
    succeeded_col = "auth_login_succeeded"
    failed_col = "auth_login_failed"
    pivot[succeeded_col] = pivot.get(succeeded_col, 0)
    pivot[failed_col] = pivot.get(failed_col, 0)

    # ── Vectorised ratio (pure Pandas, no iteration) ──────────────────────
    pivot["total"] = pivot[succeeded_col].astype(int) + pivot[failed_col].astype(int)
    pivot["failed"] = pivot[failed_col].astype(int)
    pivot["rate"] = (pivot[failed_col] / pivot["total"]).fillna(0.0).round(4)

    # Convert to native Python types and serialise (no loops)
    pivot = pivot.sort_values("day")
    pivot["day"] = pivot["day"].astype(str)
    return pivot[["day", "total", "failed", "rate"]].to_dict(orient="records")