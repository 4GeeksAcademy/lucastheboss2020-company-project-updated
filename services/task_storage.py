"""Database helpers for durable async-task audit (dead-letter queue).

Uses ``services.db_connect._connect`` — zero FastAPI / Starlette dependency.

Public functions
----------------
- ``write_dlq(...)`` — idempotent insert into ``async_task_dlq``.
- ``apply_ddl()`` — create the DLQ table (safe to call repeatedly).
"""

from __future__ import annotations

import logging

from services.db_connect import _connect

logger = logging.getLogger(__name__)

_DLQ_TABLE = "async_task_dlq"

_DDL = f"""
CREATE TABLE IF NOT EXISTS {_DLQ_TABLE} (
    id          BIGSERIAL PRIMARY KEY,
    task_id     UUID NOT NULL,
    task_name   TEXT NOT NULL,
    week_start  DATE,
    attempt     INTEGER NOT NULL,
    error       TEXT NOT NULL,
    failed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_{_DLQ_TABLE}_task_id
    ON {_DLQ_TABLE} (task_id);
"""


def read_dlq(task_id: str) -> dict | None:
    """Look up a dead-letter entry by *task_id*.

    Returns a dict with keys ``task_id``, ``task_name``, ``week_start``,
    ``attempt``, ``error``, ``failed_at``, or ``None`` if no entry exists.
    """
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT task_id, task_name, week_start, attempt, error, failed_at
                    FROM {_DLQ_TABLE}
                    WHERE task_id = %s
                    """,
                    (task_id,),
                )
                row = cur.fetchone()
        if row:
            return {
                "task_id": str(row[0]),
                "task_name": row[1],
                "week_start": str(row[2]) if row[2] else None,
                "attempt": row[3],
                "error": row[4],
                "failed_at": row[5].isoformat() if row[5] else None,
            }
        return None
    except Exception:
        logger.exception("Failed to read DLQ entry for task %s", task_id)
        return None
    finally:
        conn.close()


def apply_ddl() -> None:
    """Create the DLQ table and index if they do not exist.

    Safe to call on every startup — uses IF NOT EXISTS / IF NOT EXISTS.
    """
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                for statement in _DDL.split(";"):
                    cleaned = statement.strip()
                    if cleaned:
                        cur.execute(cleaned)
        logger.info("DLQ table %s ensured", _DLQ_TABLE)
    except Exception:
        logger.exception("Failed to create DLQ table")
        raise
    finally:
        conn.close()


def write_dlq(
    task_id: str,
    task_name: str,
    week_start: str | None,
    attempt: int,
    error: str,
) -> bool:
    """Write a dead-letter entry for an exhausted task.

    Uses ``INSERT … ON CONFLICT (task_id) DO NOTHING`` so calling this
    multiple times for the same task is safe — only the first write persists.

    Returns ``True`` on success, ``False`` if the insert failed (and logs
    the failure at ERROR level).
    """
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {_DLQ_TABLE}
                        (task_id, task_name, week_start, attempt, error)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (task_id) DO NOTHING
                    """,
                    (task_id, task_name, week_start, attempt, error),
                )
                was_inserted = cur.rowcount > 0
        if was_inserted:
            logger.info("DLQ entry written for task %s (attempt %d)", task_id, attempt)
        else:
            logger.info("DLQ entry already exists for task %s — skipped", task_id)
        return True
    except Exception:
        logger.exception("CRITICAL: failed to write DLQ entry for task %s", task_id)
        return False
    finally:
        conn.close()