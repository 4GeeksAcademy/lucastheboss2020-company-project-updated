"""Orchestration run-log for background jobs (e.g. nightly_export).

This module manages the ``job_runs`` table — a lightweight state-machine for
external scripts that need locking and idempotency guarantees.  It uses raw
psycopg2 via ``services.db_connect``, which has **zero** FastAPI / Starlette /
SQLAlchemy dependencies.

Four public functions:

1. ``create_job_run(job_name, target_date)`` — insert/reset a pending record.
2. ``update_job_run(run_id, status, error_message)`` — advance the state machine.
3. ``acquire_processing_lock(job_name, target_date)`` — **atomic** lock
   (combines insert + pending→processing in one statement).
4. ``has_completed_for_date(job_name, target_date)`` — idempotency check.

State machine::

    pending ──→ processing ──→ completed
                      │
                      └──→ failed

Distributed lock
----------------
``acquire_processing_lock`` uses a **single atomic PostgreSQL statement**
(INSERT … ON CONFLICT … DO UPDATE … WHERE status NOT IN ('processing', 'completed'))
so two script instances that start at the exact same moment cannot both acquire
the lock.  This replaces the vulnerable 3-step pattern
(has_processing_lock → INSERT → UPDATE) which had a race condition.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from psycopg2.extras import RealDictCursor

# FastAPI‑free connection helpers — see services/db_connect.py docstring.
from services.db_connect import _connect

logger = logging.getLogger(__name__)

# ── helpers ──────────────────────────────────────────────────────────────────

_JOB_RUNS_TABLE = "job_runs"


def _now() -> datetime:
    """Return the current UTC timestamp (used for started_at / finished_at)."""
    return datetime.now(timezone.utc)


# ── public API ───────────────────────────────────────────────────────────────


def create_job_run(job_name: str, target_date: date) -> dict[str, Any] | None:
    """Insert a new ``job_runs`` record with status ``pending``.

    If a row for (job_name, target_date) already exists and is **not**
    ``completed``, it is **reset** to ``pending`` — this enables automatic
    retry after a failure.  Completed rows are never overwritten because the
    caller checks ``has_completed_for_date`` first.

    Returns the full row as a dict, or ``None`` if a completed row already
    exists (the ON CONFLICT DO UPDATE … WHERE clause skips completed rows,
    so RETURNING * yields no row).

    Raises:
        RuntimeError: When no PostgreSQL DSN is configured.
        psycopg2.Error: For unexpected database errors.
    """
    conn = _connect()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"""
                    INSERT INTO {_JOB_RUNS_TABLE} (job_name, target_date, status)
                    VALUES (%s, %s, 'pending')
                    ON CONFLICT (job_name, target_date)
                    DO UPDATE SET
                        status        = 'pending',
                        started_at    = NULL,
                        finished_at   = NULL,
                        error_message  = NULL
                        WHERE {_JOB_RUNS_TABLE}.status != 'completed'
                    RETURNING *
                    """,
                    (job_name, target_date),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    finally:
        conn.close()


def update_job_run(
    run_id: int,
    status: str,
    error_message: str | None = None,
) -> dict[str, Any] | None:
    """Advance the state machine for run *run_id*.

    Automatically sets ``started_at`` when transitioning to ``processing``,
    and ``finished_at`` when transitioning to ``completed`` or ``failed``.

    Returns the updated row as a dict, or ``None`` if no row matched *run_id*.

    Raises:
        ValueError: When *status* is not one of ``processing`` / ``completed`` / ``failed``.
        RuntimeError: When no PostgreSQL DSN is configured.
        psycopg2.Error: For unexpected database errors.
    """
    valid = {"processing", "completed", "failed"}
    if status not in valid:
        raise ValueError(f"Invalid status '{status}'; expected one of {sorted(valid)}")

    now = _now()

    set_clauses = ["status = %s"]
    params: list[Any] = [status]

    if status == "processing":
        set_clauses.append("started_at = %s")
        params.append(now)
    elif status in ("completed", "failed"):
        set_clauses.append("finished_at = %s")
        params.append(now)

    if error_message is not None:
        set_clauses.append("error_message = %s")
        params.append(error_message)

    params.append(run_id)  # WHERE

    conn = _connect()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"""
                    UPDATE {_JOB_RUNS_TABLE}
                    SET {', '.join(set_clauses)}
                    WHERE id = %s
                    RETURNING *
                    """,
                    params,
                )
                row = cur.fetchone()
                return dict(row) if row else None
    finally:
        conn.close()


def acquire_processing_lock(job_name: str, target_date: date) -> dict[str, Any] | None:
    """Atomically create/update a job run and transition to ``processing``.

    This is the **distributed lock** — it combines the existence check,
    the idempotency check, and the ``pending → processing`` transition in a
    **single atomic statement**.  Two script instances that start at the exact
    same moment cannot both acquire the lock.

    Semantics
    ---------
    1. If a row already exists with status = ``'processing'`` → returns ``None``
       (lock busy — another instance is running).
    2. If a row already exists with status = ``'completed'`` → returns ``None``
       (already done for this day — idempotency).
    3. Otherwise inserts a new row, or resets an existing ``failed`` row, and
       sets status = ``'processing'`` with ``started_at = now()``.

    The WHERE clause on the UPDATE branch is::

        WHERE {table}.status NOT IN ('processing', 'completed')

    which means the ON CONFLICT DO UPDATE **does nothing** for locked/completed
    rows, so ``RETURNING *`` yields no row → the function returns ``None``.

    Returns the full row as a dict on successful lock acquisition, or ``None``
    if another instance holds the lock or the date is already completed.

    Raises:
        RuntimeError: When no PostgreSQL DSN is configured.
        psycopg2.Error: For unexpected database errors.
    """
    now = _now()
    conn = _connect()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"""
                    INSERT INTO {_JOB_RUNS_TABLE}
                        (job_name, target_date, status, started_at)
                    VALUES (%s, %s, 'processing', %s)
                    ON CONFLICT (job_name, target_date)
                    DO UPDATE SET
                        status        = 'processing',
                        started_at    = %s,
                        finished_at   = NULL,
                        error_message  = NULL
                        WHERE {_JOB_RUNS_TABLE}.status NOT IN ('processing', 'completed')
                    RETURNING *
                    """,
                    (job_name, target_date, now, now),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    finally:
        conn.close()


def has_processing_lock(job_name: str) -> bool:
    """Return ``True`` if a run for *job_name* is currently ``processing``.

    This is a **read-only** check — useful for monitoring or pre-flight
    checks, but **not for distributed locking** — use
    ``acquire_processing_lock()`` which is atomic.
    """
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT 1 FROM {_JOB_RUNS_TABLE}
                    WHERE job_name = %s AND status = 'processing'
                    LIMIT 1
                    """,
                    (job_name,),
                )
                return cur.fetchone() is not None
    finally:
        conn.close()


def has_completed_for_date(job_name: str, target_date: date) -> bool:
    """Return ``True`` if a run for (*job_name*, *target_date*) already
    reached ``completed`` status.

    This is the **idempotency** check: if the CSV was already exported and the
    pipeline was already triggered for a given day, the nightly script should
    skip that day.

    A ``failed`` run is **not** considered completed — the script should retry.
    """
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT 1 FROM {_JOB_RUNS_TABLE}
                    WHERE job_name = %s AND target_date = %s AND status = 'completed'
                    LIMIT 1
                    """,
                    (job_name, target_date),
                )
                return cur.fetchone() is not None
    finally:
        conn.close()