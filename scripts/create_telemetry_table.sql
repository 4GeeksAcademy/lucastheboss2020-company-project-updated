-- TrackFlow Telemetry Events Table (Phase 3 — Storage)
-- Run this against your Supabase PostgreSQL database via the SQL Editor.
--
-- Design invariants:
--   - Immutable — no UPDATE or DELETE on recorded telemetry (facts are facts).
--   - The fixed column set (event_type, timestamp, service) supports analytical
--     queries without JSONB traversal.
--   - tags (JSONB) stores the envelope's `properties` object as-is, so events
--     with different property schemas coexist without schema changes.
--   - service is derived from event_type prefix at insert time (e.g.
--     "inbound_order_created" → "inventory"), mirroring the event-schemas.json
--     taxonomy.entity grouping.

CREATE TABLE IF NOT EXISTS telemetry_events (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id      UUID        NOT NULL UNIQUE,       -- eventId envelope field
    timestamp     TIMESTAMPTZ NOT NULL,               -- event time (indexed below)
    session_id    TEXT,                                -- sessionId envelope field
    user_id       TEXT,                                -- userId envelope field
    event_type    TEXT        NOT NULL,                -- e.g. inbound_order_created
    schema_version INTEGER    NOT NULL DEFAULT 1,      -- schemaVersion envelope field
    request_id    TEXT,                                -- requestId envelope field
    service       TEXT        NOT NULL,                -- derived: event_type → prefix
    tags          JSONB       NOT NULL DEFAULT '{}',   -- cspell:disable-line — properties object
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  telemetry_events IS 'Immutable telemetry event log. No UPDATE/DELETE.';
COMMENT ON COLUMN telemetry_events.tags IS 'JSONB envelope properties object — per-event allowlisted fields.';
COMMENT ON COLUMN telemetry_events.service IS 'Derived service name from event_type prefix (e.g. "inventory", "auth").';

-- Indexes for analytical queries at scale (CONTEXT_6 §7).
CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp   ON telemetry_events (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_event_type  ON telemetry_events (event_type);
CREATE INDEX IF NOT EXISTS idx_telemetry_tags         ON telemetry_events USING GIN (tags);

-- Enable Row-Level Security (table is exposed via Supabase Data API).
ALTER TABLE telemetry_events ENABLE ROW LEVEL SECURITY;

-- Allow the anon role (public Data API) to INSERT only — read queries go
-- through the analytics dashboard, not the Data API.
-- The authenticated role gets INSERT + SELECT for dashboard queries.
CREATE POLICY telemetry_insert_anon ON telemetry_events
    FOR INSERT
    TO anon
    WITH CHECK (true);

CREATE POLICY telemetry_insert_auth ON telemetry_events
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

CREATE POLICY telemetry_select_auth ON telemetry_events
    FOR SELECT
    TO authenticated
    USING (true);