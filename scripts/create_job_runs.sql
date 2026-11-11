-- TrackFlow job_runs Table (Nightly Export — Background Processes)
-- Run this against your Supabase PostgreSQL database via the SQL Editor.
--
-- Design:
--   - job_name + target_date uniquely identify a run (idempotency).
--   - status is constrained via CHECK to the 4-state machine:
--     pending → processing → completed
--                   ↓
--                failed
--   - The UNIQUE index on (job_name, target_date) makes idempotency checks
--     efficient and prevents duplicate rows for the same job+day.
--   - This table is separate from reporting.pipeline_run_log (Milestone 6).
--     job_runs tracks the nightly orchestration script; pipeline_run_log
--     tracks the internal ETL phases.
--
-- Usage:
--   psql "$DATABASE_URL" -f scripts/create_job_runs.sql

CREATE TABLE IF NOT EXISTS job_runs (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_name      TEXT        NOT NULL,
    target_date   DATE        NOT NULL,
    status        TEXT        NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    error_message TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  job_runs IS 'Orchestration run log for background jobs (e.g. nightly_export).';
COMMENT ON COLUMN job_runs.job_name IS 'Logical job identifier (e.g. "nightly_export").';
COMMENT ON COLUMN job_runs.target_date IS 'Date this run targets (per-day idempotency).';
COMMENT ON COLUMN job_runs.status IS 'State machine: pending → processing → completed | failed';
COMMENT ON COLUMN job_runs.started_at IS 'Set when status transitions to processing.';
COMMENT ON COLUMN job_runs.finished_at IS 'Set when status transitions to completed or failed.';

-- Efficient idempotency lookup: (job_name, target_date) must be unique.
CREATE UNIQUE INDEX IF NOT EXISTS idx_job_runs_name_date ON job_runs (job_name, target_date);

-- Fast status queries (e.g. "is anything currently processing?").
CREATE INDEX IF NOT EXISTS idx_job_runs_status ON job_runs (status);