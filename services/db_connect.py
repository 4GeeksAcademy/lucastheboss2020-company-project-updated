"""Raw psycopg2 connection helpers — no FastAPI / SQLAlchemy dependency.

This module exists so that background scripts (``scripts/nightly_export.py``,
``services/job_runner.py``) can open a PostgreSQL connection **without**
importing the entire FastAPI / Starlette stack.  The same helpers exist in
``services/telemetry_storage.py`` (which needs the backend package for the
allowlist registry), but this module is intentionally dependency-free.

Usage::

    from services.db_connect import _connect, _get_dsn
"""

from __future__ import annotations

import os
from typing import Any

import psycopg2


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
    return (
        cleaned.startswith(("postgresql://", "postgres://", "postgresql+"))
        or "dbname=" in cleaned
    )


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