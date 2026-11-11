# TrackFlow Progress

## Completed

- TrackFlow business context and lead domain model established.
- Public website sections for services, coverage, and company positioning implemented.
- Validated information request form implemented with API submission, success/error states, comments counter, privacy requirement, and low-volume warning.
- Organization Schema.org markup added to the public website.
- Candidate CRUD and notes API implemented.
- Backoffice lead search, status filtering, stage filtering, pagination, and candidate detail links implemented.
- Agent rules, reusable TrackFlow skill guidance, and structured memory-bank documentation added.

## Current Milestone

Milestone 4 evaluation readiness: confirm documentation structure, public lead capture, internal lead operations, API behavior, and production build.

## Next Checks

- Verify the evaluation checklist against all criteria (14/14 passed for incident analysis pipeline).
- Run typecheck and production build before staging.
- Confirm generated build directories remain excluded from commits.

## Recent Completions (Incident Analysis Pipeline)

### Script (`scripts/analyze_incidents.py`)
- ✅ Accepts CSV path as CLI argument
- ✅ Detects invalid records with specific error messages (email, phone, date, category, status, satisfaction score, missing fields)
- ✅ Reports 6+ metrics (total, valid, invalid, category breakdown, status breakdown, satisfaction index)
- ✅ Human-readable console output with clear sections, separators, and alignment
- ✅ Interactive export prompt → saves results.csv (one row per metric)
- ✅ JSON output preserved for API consumption

### Backend API (`app/api/incidents/`)
- ✅ `POST /api/incidents/analyze` — accepts CSV as multipart, returns JSON
- ✅ `GET /api/incidents/results` — retrieve stored analyses (all or by ID)
- ✅ `GET /api/incidents/results/export` — latest analysis as CSV download
- ✅ `GET /api/incidents/results/[id]/export` — specific analysis as CSV download
- ✅ Proper HTTP status codes (400, 404, 500) with descriptive messages

### Frontend (`uis/backoffice/IncidentAnalyzer.tsx`)
- ✅ Drag-and-drop + file input CSV upload
- ✅ Results summary on screen (total, valid, invalid, category/status breakdowns, satisfaction)
- ✅ Export CSV button with blob download
- ✅ Red alert banner with error type aggregation badges (e.g., "3x Invalid email")
- ✅ Expandable invalid record details per row
- ✅ Analysis history navigation
- ✅ Accessible from navigation and BackofficeHome page

### CONTEXT.md
- ✅ Added "Incident Analysis — Expected Results" section with exact values for both test CSV files

### Evaluation
- ✅ 14/14 criteria PASSED (documented in BACKEND_EVALUATION_REPORT.md)

## Recent Completions (Telemetry Foundation — Phase 2)

### Single source of truth (`event-schemas.json`)
- ✅ 35 known telemetry events defined with double-nested property allowlists and `additionalProperties: false` (schema-validated envelope constraints)
- ✅ Role enums (`user`/`manager`/`admin`) and reason enums for login-failed / session-expired / registration-failed events

### Backend telemetry package (`backend/telemetry/`)
- ✅ `core.py` — envelope builder (eventId UUID, ISO-8601 ms UTC timestamp, sessionId/userId default "anonymous", requestId via ContextVar), `emit` with schema validation + auto-flush at 1000, `emit_threshold` with once-per-UTC-day dedupe, `flush` to TELEMETRY_SINK_PATH (JSONL), `reset_state_for_tests` clears buffer/threshold cache **in place** (no stale references across resets)
- ✅ `registry.py` — loads event-schemas.json once (lru_cache), exposes KNOWN_EVENTS + allowlist + `validate_event`
- ✅ `context.py` — warehouse/client/country normalization + client_id slugging (lru_cache), configurable TELEMETRY_LOW_STOCK_THRESHOLD (default 20)
- ✅ `inventory_events.py` — inbound/outbound/threshold/rejection emit helpers + `inventory_context` (returns {} when required context unavailable — PII-safe)
- ✅ `auth_events.py` — login succeeded/failed (sanitised, never carries credentials), registration created/failed, password reset requested/completed (no email/token in events), password changed, session expired/ended + region=ES
- ✅ `middleware.py` — single `TelemetryMiddleware` (replaces old timing decorator, preserves exact log line), honors inbound `X-Request-Id` or generates one (echoed on response), emits `api_latency_recorded` (sampled) / `api_error`, ignores health/docs traffic, 4xx → latency only

### Instrumented endpoints
- ✅ `backend/main.py` — login (succeeded/failed incl. account_disabled), registration (created/email_conflict), forgot_password (issued flag, PII-safe), reset_password (success/failure), change_password (source=profile); `install_telemetry(app)` wired after error handlers
- ✅ `backend/auth.py` — `get_current_user` emits `session_expired` with reason (token_expired / invalid_token / user_inactive / missing_token) via OAuth2 dependency
- ✅ `services/routers/inventory.py` — `inventory_order_created` (inbound), `inventory_order_created` outbound + low-stock `stock_threshold_triggered`, `outbound_order_rejected` with reason (warehouse_mismatch / insufficient_stock / validation_failed); `emit_direct_stock_edit_rejected` + `emit_inventory_discrepancy_detected` imported for the batch-audit/direct-write milestone (no call site yet)

### Verification
- ✅ 139/139 tests pass (includes 21 telemetry tests: registry floor, normalization, envelope validation, HTTP-level auth sanitisation + X-Request-Id correlation)
- ✅ All modified files compile (`py_compile`); `npm run typecheck` clean
- ✅ End-to-end probe (deleted after use) confirmed 401/500 correlation + JSONL sink flush

### Telemetry Plan doc persisted (evaluation closure)
- ✅ `docs/TELEMETRY_PLAN.md` created and grounded 1:1 against `event-schemas.json` (35 events: hypothesis → decision for every event, stream/batch justification by business urgency, PII & sanitisation table, risks & exclusions, implementation notes, consistency statement)
- ✅ Closes the eval-criteria gaps #3 / #6 / #7 / #9: the plan the evaluation cross-references now exists in the repo

## Next Checks (Telemetry)
- Frontend instrumentation (Phase 3) — browser telemetry events per the plan
- Batch jobs: nightly inventory audit → `inventory_discrepancy_detected`; direct-write guard → `direct_stock_edit_rejected`
- Stream vs batch delivery, redaction pipeline, archival at the storage layer
- Wire `direct_stock_edit_rejected` / `inventory_discrepancy_detected` call sites at their milestone (helpers already imported)

## Recent Completions (Telemetry — Phase 3 Storage + Resubmit)
- ✅ `scripts/create_telemetry_table.sql` — append-only `telemetry_events` DDL (identity PK, `event_id` UNIQUE, indexed timestamp/event_type/GIN tags, RLS anon/auth insert + auth select)
- ✅ `services/telemetry_storage.py` — psycopg2 `execute_values` bulk insert with `ON CONFLICT (event_id) DO NOTHING`; DSN from `TELEMETRY_DATABASE_URL`/`DATABASE_URL` (PostgreSQL-only, RuntimeError otherwise); `derive_service` from event_type prefix
- ✅ `services/routers/telemetry.py` — POST `/telemetry/events` loose per-event Pydantic validation → `{received, stored, rejected}`; GET `/telemetry/report` (Phase 4) cached metrics
- ✅ `backend/main.py` — removed hardcoded-credential `/telemetry/events` handler
- ✅ **Resubmit: allowlist trimming before insert** — `trim_properties_to_allowlist` in storage drops out-of-plan `properties` keys (per `get_properties_allowlist`) before writing `tags` JSONB; endpoint contract unchanged
- ✅ `scripts/seed_telemetry_proof.py` + `docs/telemetry-phase3-proof.md` — seed+verify+trimming-evidence tooling for the Supabase screenshot proof
- ✅ Verification: 179/179 tests pass (49 telemetry incl. 16 telemetry-events tests, 5 new trimming tests); ruff clean on changed files
