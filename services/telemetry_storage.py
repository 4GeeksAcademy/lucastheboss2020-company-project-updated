"""Telemetry persistence layer — bulk insert into Supabase telemetry_events.

Design (TELEMETRY_PLAN Phase 3):
- Single transaction per batch: all valid events in a call are inserted atomically.
- Uses the existing SQLAlchemy engine from ``services.database`` (or a direct
  psycopg2 connection from ``DATABASE_URL``) — no new connection pool needed.
- The ``tags`` column stores the envelope ``properties`` object as JSONB.
- ``service`` is derived from ``event_type`` at insert time.

Usage::

    from services.telemetry_storage import insert_telemetry_events
    stored = insert_telemetry_events(valid_dicts)

Reference: README Phase 3 — Bulk Insert, Complementary Knowledge.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import psycopg2
from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)


# ── service derivation ───────────────────────────────────────────────────────
# Maps the first segment of event_type (before the first ``_``) to the
# analytical service name.  Unknown prefixes are kept as-is.
_SERVICE_MAP: dict[str, str] = {
    "auth": "auth",
    "session": "auth",
    "frontend": "frontend",
    "page": "frontend",
    "flow": "frontend",
    "api": "api",
    "inbound": "inventory",
    "outbound": "inventory",
    "stock": "inventory",
    "direct": "inventory",
    "inventory": "inventory",
    "candidate": "crm",
    "lead": "crm",
    "incident": "incidents",
    "supplier": "suppliers",
}


def derive_service(event_type: str) -> str:
    """Map an event_type (e.g. ``inbound_order_created``) to a service name.

    Falls back to the first segment of the event_type when no explicit mapping
    exists (e.g. ``custom_event`` → ``"custom"``).
    """
    prefix = event_type.split("_", maxsplit=1)[0] if "_" in event_type else event_type
    return _SERVICE_MAP.get(prefix, prefix)


# ── connection helpers ───────────────────────────────────────────────────────

def _get_dsn() -> str:
    """Return the DSN for the telemetry database.

    Respects ``TELEMETRY_DATABASE_URL`` when set; otherwise falls back to
    ``DATABASE_URL`` (the inventory service connection).  This lets the telemetry
    table live in the same Supabase project while keeping the option to separate
    concerns later.

    Returns an empty string when neither env var is set (callers treat this as
    "no storage configured").
    """
    return os.getenv("TELEMETRY_DATABASE_URL") or os.getenv("DATABASE_URL") or ""


def _dsn_is_postgres(dsn: str) -> bool:
    """Check whether *dsn* targets a PostgreSQL database."""
    cleaned = dsn.strip().lower()
    # PostgreSQL DSNs start with ``postgresql://``, ``postgres://``, or contain
    # ``host=`` / ``dbname=`` key-value pairs.  SQLite DSNs use ``sqlite://``.
    return cleaned.startswith(("postgresql://", "postgres://", "postgresql+")) or "dbname=" in cleaned


def _connect() -> Any:
    """Return a raw psycopg2 connection (not from the SQLAlchemy pool).

    Telemetry bulk inserts are infrequent (every 10 s per client) and using a
    dedicated connection avoids mixing transactional concerns with the inventory
    service.

    Raises:
        RuntimeError: When no PostgreSQL DSN is configured.
    """
    dsn = _get_dsn()
    if not dsn:
        raise RuntimeError(
            "TELEMETRY_DATABASE_URL or DATABASE_URL must be set to persist telemetry events."
        )
    if not _dsn_is_postgres(dsn):
        raise RuntimeError(
            f"Telemetry storage requires a PostgreSQL DSN; got a DSN that does not appear "
            f"to be PostgreSQL: {dsn[:40]}…  Configure TELEMETRY_DATABASE_URL or set "
            f"DATABASE_URL to a PostgreSQL connection string."
        )
    return psycopg2.connect(dsn, connect_timeout=5)


# ── bulk insert ──────────────────────────────────────────────────────────────

_INSERT_SQL = """\
INSERT INTO telemetry_events
    (event_id, timestamp, session_id, user_id, event_type,
     schema_version, request_id, service, tags)
VALUES %s
ON CONFLICT (event_id) DO NOTHING
"""


def _prepare_rows(valid_events: list[dict[str, Any]]) -> list[tuple]:
    """Transform validated TelemetryEvent dicts into DB row tuples."""
    rows: list[tuple] = []
    for ev in valid_events:
        rows.append((
            ev.get("eventId"),
            ev.get("timestamp"),
            ev.get("sessionId"),
            ev.get("userId"),
            ev.get("event_type"),
            ev.get("schemaVersion", 1),
            ev.get("requestId"),
            derive_service(ev.get("event_type", "")),
            # The envelope ``properties`` field maps to the DB ``tags`` column.
            # psycopg2 adapts dict → JSONB automatically when the column is JSONB.
            ev.get("properties", {}),
        ))
    return rows


def insert_telemetry_events(valid_events: list[dict[str, Any]]) -> int:
    """Persist validated telemetry events in a single bulk INSERT.

    Args:
        valid_events: List of validated ``TelemetryEvent.model_dump()`` dicts.

    Returns:
        Number of rows actually inserted (may be less than input length when
        ``event_id`` duplicates are silently skipped via ``ON CONFLICT DO NOTHING``).

    Raises:
        RuntimeError: When no database URL is configured.
        psycopg2.Error: When the INSERT fails (caller should let it propagate so
            the endpoint can return a meaningful error response).
    """
    if not valid_events:
        return 0

    rows = _prepare_rows(valid_events)
    conn = _connect()
    try:
        with conn.cursor() as cur:
            execute_values(cur, _INSERT_SQL, rows, template=None)
        conn.commit()
        return len(rows)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()