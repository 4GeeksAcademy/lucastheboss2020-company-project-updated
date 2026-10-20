# `scripts` folder

This folder contains **helper scripts** for the monorepo: development automation, maintenance utilities, repetitive tasks (setup, lint, migrations, data generation, etc.), and internal tooling.

- **Main purpose**: group support tools that do not belong to a specific app, agent, or pipeline but make the team’s work easier.
- **Recommendation**: document each script (what it does, parameters, requirements, usage examples) and keep them reproducible (and safe) across environments.

> _Spanish version: [README.es.md](./README.es.md)._

## Telemetry storage proof — `seed_telemetry_proof.py`

Seeds + verifies rows in the Supabase `telemetry_events` table for the Phase 3
storage deliverable (companion to `create_telemetry_table.sql`).

- **Seeds** deterministic events through the exact production persistence path
  (`services.telemetry_storage.insert_telemetry_events`), so `event_type` and
  allowlist-trimmed `tags` JSONB land exactly as the endpoint would produce them.
- **Verifies** by querying back the most-recent rows and printing a tabular
  report (event_type / service / tags) plus explicit **trimming evidence** — one
  seeded event carries out-of-plan keys (`password_raw`, `tracking_number`) and
  the report confirms they are stripped from `tags` before INSERT.

```bash
# Apply the DDL first (Supabase SQL editor): scripts/create_telemetry_table.sql

# Seed a batch and print the proof table (for your screenshot):
TELEMETRY_DATABASE_URL=postgresql://... python -m scripts.seed_telemetry_proof

# Just show what's already in the table (no inserts):
TELEMETRY_DATABASE_URL=postgresql://... python -m scripts.seed_telemetry_proof --verify-only

# Seed a bigger batch:
TELEMETRY_DATABASE_URL=postgresql://... python -m scripts.seed_telemetry_proof --count 20
```

`TELEMETRY_DATABASE_URL` or `DATABASE_URL` must point at the Supabase PostgreSQL
database and the table must already exist. Exit code `0` = success; the report
ends with a clear ✅/❌ trimming verdict before you screenshot it.
