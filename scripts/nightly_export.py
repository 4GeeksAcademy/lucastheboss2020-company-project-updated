#!/usr/bin/env python3
"""Nightly Export Script — Background Processes Module.

Exports telemetry_events for a given target date to CSV, then triggers the
weekly-client-performance pipeline (data/pipelines/pipeline.py).

Usage
-----
    python scripts/nightly_export.py              # target = yesterday UTC
    TARGET_DATE=2026-10-21 python scripts/nightly_export.py  # explicit date

State machine
-------------
    pending → processing → completed
                  ↓
               failed

Lock
----
Uses ``acquire_processing_lock()`` — a **single atomic PostgreSQL statement**
(INSERT … ON CONFLICT … DO UPDATE … WHERE status NOT IN ('processing','completed')).
Two script instances that start at the exact same moment cannot both acquire
the lock.

Idempotency
-----------
If a ``completed`` record already exists for (job_name='nightly_export',
target_date), the atomic lock returns ``None``, so the script does not
re-export the CSV or re-trigger the pipeline.

Failure guarantee
-----------------
Any unhandled exception is caught by the try/except block, which transitions
the job to ``failed`` with the error message.  No record remains in
``processing`` status after failure.

Design requirements
-------------------
- The script is executable directly from the command line::
    python scripts/nightly_export.py
- Do **not** run inside the FastAPI process (no APScheduler, @repeat_every, or
  lifespan hooks) — use OS crontab or similar external scheduler.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.job_runner import acquire_processing_lock, update_job_run
from services.db_connect import _connect

logger = logging.getLogger(__name__)

# ── constants ────────────────────────────────────────────────────────────────

JOB_NAME = "nightly_export"
RAW_DIR = PROJECT_ROOT / "data" / "raw"

# ── helpers ──────────────────────────────────────────────────────────────────


def _resolve_target_date() -> date:
    """Return the target date from ``TARGET_DATE`` env var or yesterday UTC."""
    raw = os.environ.get("TARGET_DATE")
    if raw:
        try:
            return date.fromisoformat(raw.strip())
        except ValueError:
            logger.warning("Invalid TARGET_DATE '%s' — falling back to yesterday", raw)
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    return yesterday.date()


def _export_csv(target_date: date) -> Path:
    """Query all telemetry_events for *target_date* and write to a CSV file.

    Returns the path to the written CSV file.

    The CSV includes all columns from the telemetry_events table in logical
    order.  The ``tags`` JSONB column is dumped as a JSON string so it can be
    re-parsed downstream (e.g. by the pipeline).
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RAW_DIR / f"telemetry_{target_date.isoformat()}.csv"

    conn = _connect()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    id,
                    event_id,
                    "timestamp",
                    session_id,
                    user_id,
                    event_type,
                    schema_version,
                    request_id,
                    service,
                    tags
                FROM telemetry_events
                WHERE "timestamp"::date = %s
                ORDER BY "timestamp" ASC
                """,
                (target_date,),
            )
            rows = cur.fetchall()
        conn.commit()
    finally:
        conn.close()

    logger.info("Exported %d telemetry events for %s", len(rows), target_date)

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id",
            "event_id",
            "timestamp",
            "session_id",
            "user_id",
            "event_type",
            "schema_version",
            "request_id",
            "service",
            "tags",
        ])
        for row in rows:
            writer.writerow([
                row["id"],
                row["event_id"],
                row["timestamp"].isoformat() if row["timestamp"] else "",
                row["session_id"],
                row["user_id"],
                row["event_type"],
                row["schema_version"],
                row["request_id"],
                row["service"],
                json.dumps(row["tags"], ensure_ascii=False) if row["tags"] else "",
            ])

    logger.info("CSV written to %s", csv_path)
    return csv_path


def _run_pipeline(target_date: date) -> None:
    """Trigger the weekly-client-performance pipeline via subprocess.

    The pipeline reads its own input data (it expects a CSV or database
    connection — see ``data/pipelines/pipeline.py``).  We pass the target
    date as the CLI argument.

    Raises:
        subprocess.CalledProcessError: When the pipeline exits non-zero.
    """
    pipeline_script = PROJECT_ROOT / "data" / "pipelines" / "pipeline.py"
    cmd = [sys.executable, str(pipeline_script), target_date.isoformat()]

    logger.info("Pipeline command: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.stdout:
        logger.info("Pipeline stdout:\n%s", result.stdout)
    if result.stderr:
        logger.warning("Pipeline stderr:\n%s", result.stderr)

    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr
        )

    logger.info("Pipeline completed successfully (exit code 0)")


# ── main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    """Orchestrate the nightly export: lock → export → pipeline.

    This function is also importable so it can be called from tests without
    a subprocess.
    """
    target_date = _resolve_target_date()

    # ── Atomic lock + idempotency check ─────────────────────────────────────
    run = acquire_processing_lock(JOB_NAME, target_date)
    if run is None:
        logger.info(
            "Aborting nightly_export for %s: "
            "another instance is already processing OR this date is already completed",
            target_date,
        )
        return

    run_id: int = run["id"]
    logger.info("nightly_export started for %s (run_id=%d)", target_date, run_id)

    try:
        # ── Export CSV ──────────────────────────────────────────────────────
        csv_path = _export_csv(target_date)

        # ── Trigger pipeline ────────────────────────────────────────────────
        _run_pipeline(target_date)

        # ── Mark as completed ───────────────────────────────────────────────
        update_job_run(run_id, "completed")
        logger.info("nightly_export completed for %s (run_id=%d)", target_date, run_id)

    except Exception:
        logger.exception("nightly_export failed for %s", target_date)
        try:
            update_job_run(run_id, "failed", error_message=str(sys.exc_info()[1]))
        except Exception as e:
            logger.error("Failed to update job_runs status to failed: %s", e)
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    main()