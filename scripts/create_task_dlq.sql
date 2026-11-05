-- Dead-Letter Queue for exhausted async Celery tasks.
--
-- Stores one row per unique task_id at the moment of terminal (final)
-- failure.  Re-running the same exhausted task_id does not create a
-- duplicate (INSERT … ON CONFLICT … DO NOTHING).
--
-- This table lives in the "public" schema (or whichever schema the
-- TELEMETRY_DATABASE_URL / DATABASE_URL targets).  It is a server-side
-- audit table — do NOT grant USAGE/SELECT to anon or authenticated
-- Supabase roles unless an explicit access need arises.

CREATE TABLE IF NOT EXISTS async_task_dlq (
    id          BIGSERIAL PRIMARY KEY,
    task_id     UUID NOT NULL,
    task_name   TEXT NOT NULL,
    week_start  DATE,                      -- business reference (reporting pipeline)
    attempt     INTEGER NOT NULL,          -- 1-based attempt that failed
    error       TEXT NOT NULL,             -- final error message (no traceback/PII)
    failed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Prevent duplicate dead-letter entries for the same task.
CREATE UNIQUE INDEX IF NOT EXISTS idx_async_task_dlq_task_id
    ON async_task_dlq (task_id);