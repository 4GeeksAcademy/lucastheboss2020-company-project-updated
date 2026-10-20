# Pipeline Design — Business Performance Report

> **Deliverable:** Weekly Warehouse & Client Performance Report for Thomas (CEO) and Ana (Head of Warehouse Operations).
>
> **Cadence:** Weekly, fresh Monday morning UTC.
>
> **Audience:** Non-technical leadership — numbers, not raw events.

---

## Table of Contents

1. [Current State Analysis](#phase-1--current-state-analysis)
2. [Pipeline Design](#phase-2--pipeline-design)
3. [Resilience & Idempotency](#phase-3--resilience--idempotency)
4. [Prefect Mapping](#phase-4--prefect-mapping)
5. [Application Integration](#phase-5--application-integration)

---

## Phase 1 — Current State Analysis

### 1.1 What exists today

TrackFlow already has an end-to-end **telemetry system** that captures inventory events and exposes them through two channels:

| Layer | Component | Purpose |
|-------|-----------|---------|
| **Capture** | `backend/telemetry/inventory_events.py` | 5 mandatory event emitters (`inbound_order_created`, `outbound_order_created`, `stock_threshold_triggered`, `direct_stock_edit_rejected`, `inventory_discrepancy_detected`) |
| **Storage** | `services/telemetry_storage.py` | Bulk insert via `psycopg2.execute_values` into `telemetry_events` table (Supabase PostgreSQL) |
| **Analysis** | `services/telemetry/analysis.py` | 4 metric functions (`events_per_day`, `error_rate_by_type`, `event_type_distribution`, `auth_failure_rate`) for the **Technical Report** |
| **API** | `GET /telemetry/report` | Phase 4 endpoint with 60-second cache returning operational metrics |
| **Dashboard** | `uis/backoffice/telemetry/` | Frontend page displaying the Technical Report charts |

### 1.2 The gap

The existing Technical Report (`GET /telemetry/report`) answers engineering questions: *How many events per day? What is the error rate by type?* It does **not** answer the business questions Thomas and Ana need:

| Question | Existing report | Needed |
|----------|-----------------|--------|
| *How many units arrived at Los Angeles for Fashion Co this week?* | ❌ | ✅ Inbound Volume KPI |
| *How many orders did Zaragoza dispatch for ElectroBrand?* | ❌ | ✅ Outbound Throughput KPI |
| *Did any warehouse run out of stock for a client this week?* | ❌ | ✅ Stockout Frequency KPI |
| *Which warehouse-client pair has the highest discrepancy rate?* | ❌ | ✅ Discrepancy Rate KPI |

**The gap is aggregation grain.** The Technical Report aggregates across all dimensions (time series by day, error rates globally). The business report needs **multi-dimensional aggregation**: per warehouse × per client × per ISO week.

### 1.3 Constraints and non-goals

- **Do NOT modify** `services/telemetry/analysis.py` or `GET /telemetry/report` — the Technical Report is out of scope for this milestone.
- **Do NOT write** to `telemetry_events` — pipeline is read-only on the source.
- **Do NOT aggregate across clients** — each row belongs to a single client.

---

## Phase 2 — Pipeline Design

### 2.1 Architecture overview

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────────────────┐
│ telemetry    │     │  Extract (SQL)    │     │  Transform (Pandas)         │
│ _events      │────▶│                   │────▶│                             │
│ (PostgreSQL) │     │  Filter 4 event   │     │  GroupBy: warehouse         │
│              │     │  types in range   │     │  + client_id + ISO week     │
└──────────────┘     │  read-only query  │     │  Vectorised agg:            │
                     └──────────────────┘     │  • SUM(quantity) inbound    │
                                              │  • COUNT outbound orders    │
                     ┌──────────────────┐     │  • COUNT stock thresholds   │
                     │  Load (Upsert)    │     │  • COUNT discrepancies      │
                     │                   │◀────│  • rate = disc / outbound   │
                     │ PostgreSQL        │     └─────────────────────────────┘
                     │ reporting.        │
                     │ weekly_warehouse_ │
                     │ client_performance│
                     └──────────────────┘
```

### 2.2 Extract — SQL over `telemetry_events`

**Connection:** Reuse the `_connect()` helper from `services.telemetry_storage.py`. It reads `TELEMETRY_DATABASE_URL` (fallback `DATABASE_URL`) and returns a raw `psycopg2` connection — the same pattern already proven in `services/telemetry/analysis.py`.

**Query logic:**

```sql
SELECT
  tags->>'warehouse'                          AS warehouse,
  tags->>'client_id'                          AS client_id,
  DATE_TRUNC('week', timestamp::date)::date   AS week_start,
  event_type,
  -- quantity lives at tags->>'quantity'; cast to integer for SUM
  COALESCE((tags->>'quantity')::integer, 0)   AS quantity
FROM telemetry_events
WHERE event_type IN (
      'inbound_order_created',
      'outbound_order_created',
      'stock_threshold_triggered',
      'inventory_discrepancy_detected'
  )
  AND timestamp >= %(start)s
  AND timestamp <  %(end)s
```

**Design decisions:**

- `tags->>'warehouse'` and `tags->>'client_id'` are extracted as text — the `inventory_context()` helper in `backend/telemetry/inventory_events.py` always sets these when building the properties dict, and `_prepare_rows()` in `telemetry_storage.py` stores `properties` as the `tags` JSONB column.
- `quantity` is cast to `integer` at query time. Both `inbound_order_created` and `outbound_order_created` carry `quantity` in their properties. `stock_threshold_triggered` also carries `quantity` (the current stock level) but that is counted, not summed.
- `DATE_TRUNC('week', ...)` gives the Monday of the week in UTC, matching the ISO week grain.
- A parameterised `%(start)s`/`%(end)s` window avoids full-table scans and makes the pipeline naturally restartable (see Phase 3).
- No JOINs needed — all dimension data (warehouse, client_id) is denormalised into the event's `tags` JSONB column.

### 2.3 Transform — Pandas vectorised aggregation

**Tool:** Pandas `groupby().agg()`, the same vectorised pattern already used in `services/telemetry/analysis.py`.

**Steps:**

```
1. Load query result into DataFrame (pd.read_sql)
2. Separate rows by event_type into 4 filtered views
3. Group each view by [warehouse, client_id, week_start]
4. Compute:
   - inbound_units_count   = SUM(quantity) for inbound_order_created
   - outbound_orders_count = COUNT(*)    for outbound_order_created
   - stockout_events_count = COUNT(*)    for stock_threshold_triggered
   - discrepancy_events_count = COUNT(*) for inventory_discrepancy_detected
5. Merge the 4 aggregated results on [warehouse, client_id, week_start]
6. Fill NaN with 0 (a warehouse-client may have 0 stockouts = 0 rows in that view)
7. Compute discrepancy_rate = discrepancy_events_count / outbound_orders_count
   (0 when outbound_orders_count = 0, via fillna(0))
8. Add computed_at = datetime.now(timezone.utc)
```

**Why Pandas and not pure SQL:** Pandas handles the merge of 4 differently-shaped aggregations (SUM vs COUNT, with different column names) more cleanly than a single SQL query with `CASE WHEN` expressions. A pure-SQL alternative is documented in appendix A for future optimisation.

**Why not a Python loop:** The entire transform uses vectorised Pandas operations — no `for _, row in df.iterrows()` — mirroring the constraint already enforced in `analysis.py`.

### 2.4 Load — Upsert into reporting table

**Tool:** `psycopg2.execute_values` with `ON CONFLICT` — the same bulk-insert pattern used in `services/telemetry_storage.py`.

```sql
INSERT INTO reporting.weekly_warehouse_client_performance
    (warehouse, client_id, week_start, inbound_units_count,
     outbound_orders_count, stockout_events_count,
     discrepancy_events_count, discrepancy_rate, computed_at)
VALUES %s
ON CONFLICT (warehouse, client_id, week_start)
DO UPDATE SET
    inbound_units_count       = EXCLUDED.inbound_units_count,
    outbound_orders_count     = EXCLUDED.outbound_orders_count,
    stockout_events_count     = EXCLUDED.stockout_events_count,
    discrepancy_events_count  = EXCLUDED.discrepancy_events_count,
    discrepancy_rate          = EXCLUDED.discrepancy_rate,
    computed_at               = EXCLUDED.computed_at;
```

**Design decisions:**

- **Upsert (ON CONFLICT DO UPDATE)** makes the pipeline fully idempotent — re-running the same week overwrites, does not duplicate.
- **`computed_at` is updated** so downstream consumers know when the data was last refreshed.
- **`id` (UUID) is NOT in the INSERT** — it uses `gen_random_uuid()` default, so each upsert generates a new UUID. This is acceptable because the `UNIQUE` constraint is on the business key, and old UUIDs are never referenced externally.

### 2.5 SQL DDL — Production setup

```sql
CREATE SCHEMA IF NOT EXISTS reporting;

CREATE TABLE IF NOT EXISTS reporting.weekly_warehouse_client_performance (
  id uuid primary key default gen_random_uuid(),
  warehouse text not null,
  client_id text not null,
  week_start date not null,
  inbound_units_count integer not null default 0,
  outbound_orders_count integer not null default 0,
  stockout_events_count integer not null default 0,
  discrepancy_events_count integer not null default 0,
  discrepancy_rate numeric not null default 0,
  computed_at timestamptz not null default now(),
  unique (warehouse, client_id, week_start)
);

-- Index for typical query patterns
CREATE INDEX IF NOT EXISTS idx_weekly_perf_week_start
  ON reporting.weekly_warehouse_client_performance (week_start DESC);
```

---

## Phase 3 — Resilience & Idempotency

### 3.1 Idempotency strategy

| Risk | Mitigation |
|------|-----------|
| Pipeline runs twice for the same week | `ON CONFLICT (warehouse, client_id, week_start) DO UPDATE` — upsert semantics mean the second run overwrites with the same data |
| Partial failure mid-batch | `execute_values` runs in a single transaction; if any row fails, the entire batch rolls back. The pipeline can be re-run safely. |
| Duplicate events in `telemetry_events` | `telemetry_events` has an `ON CONFLICT (event_id) DO NOTHING` (from Phase 3 storage), so the source is already deduplicated at insert time. |
| Same event counted across two pipeline runs | The pipeline uses a `[start, end)` timestamp window. If the window is stable (always the same ISO week), the same events are counted. If a late-arriving event falls into the window, it is picked up on re-run — this is **desired behaviour** (the number should reflect the final state). |

### 3.2 Recoverability — Watermark table

To support exactly-once semantics and avoid full historical re-scans on every run, introduce a lightweight **watermark table** in the `reporting` schema:

```sql
CREATE TABLE IF NOT EXISTS reporting.pipeline_watermark (
  pipeline_name text primary key,
  last_completed_week date not null,   -- the week_start that was fully processed
  last_run_at timestamptz not null default now(),
  status text not null default 'success'  -- 'success' | 'failed'
);
```

**Recovery flow:**

```
1. READ watermark → get last_completed_week
2. Compute next_week = last_completed_week + 7 days
3. If next_week <= current_week:
     RUN(next_week)
     UPDATE watermark SET last_completed_week = next_week, status = 'success'
     GOTO step 2
   Else:
     SLEEP until next Monday
```

This handles:

- **Process crash mid-run:** On restart, the watermark still points to the last fully-completed week. The pipeline skips that week and starts from the next.
- **Catch-up after downtime:** If the pipeline was off for 3 weeks, it processes weeks 1, 2, 3 sequentially — each producing a correct upsert.
- **Manual backfill:** Setting `last_completed_week` to an earlier date triggers re-processing of all subsequent weeks.

### 3.3 Observability

| What to observe | How |
|----------------|-----|
| Rows extracted | Log `SELECT COUNT(*)` per event type before grouping |
| Rows inserted/updated | Capture `cursor.rowcount` after `execute_values` |
| Duration | `time.perf_counter()` around each phase (extract / transform / load) |
| Errors | Catch exceptions at pipeline level, log full traceback, write `status='failed'` to watermark |
| Missing weeks | Compare watermark `last_completed_week` against `DATE_TRUNC('week', NOW())` — alert if gap > 7 days |

### 3.4 Input validation at pipeline entry

Before executing, validate:

1. `week_start` is a Monday (`week_start.weekday() == 0`)
2. `week_start` is not in the future
3. `week_start` is not more than 365 days in the past (safety guardrail)
4. PostgreSQL is reachable via `_connect()`
5. Destination table exists (or run DDL)


### 3.5 Execution audit log

Every pipeline run records an entry in the `reporting.pipeline_run_log` table with at least the following fields for full auditability:

| Field | Data type | Justification |
|-------|-----------|---------------|
| `run_id` | `UUID` (PK) | Unique identifier per execution — links to application logs and enables trace-by-run queries |
| `pipeline_name` | `TEXT` | Identifies which pipeline (supports multiple pipelines in the future) |
| `week_start` | `DATE` | The ISO week being processed — links the audit row to the output data grain |
| `status` | `TEXT` | `'running'` / `'success'` / `'failed'` — enables alerting, dashboards, and rollback detection |
| `rows_extracted` | `INTEGER` | Number of raw events pulled from `telemetry_events` — compare against `rows_upserted` to detect data loss |
| `rows_upserted` | `INTEGER` | Number of rows written into `weekly_warehouse_client_performance` — validates transform completeness |
| `error_message` | `TEXT` | `NULL` on success, full traceback on failure — essential for post-mortem debugging without log scraping |
| `started_at` | `TIMESTAMPTZ` | When execution began — feeds duration and SLA tracking |
| `completed_at` | `TIMESTAMPTZ` | When execution finished — feeds duration and SLA tracking |

```sql
CREATE TABLE IF NOT EXISTS reporting.pipeline_run_log (
  run_id uuid primary key default gen_random_uuid(),
  pipeline_name text not null,
  week_start date not null,
  status text not null default 'running',
  rows_extracted integer not null default 0,
  rows_upserted integer not null default 0,
  error_message text,
  started_at timestamptz not null default now(),
  completed_at timestamptz
);
```

> **Design choice:** The run log is written **before** the pipeline starts (status = `'running'`) and **updated** on completion. If the process crashes mid-run, the dangling `'running'` entry signals an incomplete execution — exactly the pattern required for operational observability.

---

## Phase 4 — Prefect Mapping

### 4.1 Flow and task hierarchy

```
┌──────────────────────────────────────────────────┐
│  weekly_client_performance_pipeline (Flow)        │
│  Parameters: week_start: str (ISO date, Monday)   │
│                                                    │
│  ┌──────────────────────┐                          │
│  │ extract_events       │  Task                    │
│  │ Input:  week_start   │                          │
│  │ Output: pd.DataFrame │                          │
│  │ (raw events for week)│                          │
│  └──────┬───────────────┘                          │
│         │                                           │
│         ▼                                           │
│  ┌──────────────────────┐                          │
│  │ transform_to_kpis    │  Task                    │
│  │ Input:  raw_df       │                          │
│  │ Output: pd.DataFrame │                          │
│  │ (aggregated KPIs)    │                          │
│  └──────┬───────────────┘                          │
│         │                                           │
│         ▼                                           │
│  ┌──────────────────────┐                          │
│  │ load_to_reporting    │  Task                    │
│  │ Input:  kpi_df       │                          │
│  │ Output: int (rows    │                          │
│  │         upserted)    │                          │
│  └──────┬───────────────┘                          │
│         │                                           │
│         ▼                                           │
│  ┌──────────────────────┐                          │
│  │ record_watermark     │  Task                    │
│  │ Input:  week_start,  │                          │
│  │         status       │                          │
│  └──────────────────────┘                          │
└──────────────────────────────────────────────────┘
```

### 4.2 State machine

```
         ┌──────────┐
         │ SCHEDULED │  (Cron: every Monday 01:00 UTC)
         └────┬─────┘
              │
              ▼
         ┌──────────┐
         │  RUNNING │
         └────┬─────┘
              │
       ┌──────┴──────┐
       │             │
       ▼             ▼
   ┌────────┐  ┌──────────┐
   │ SUCCESS│  │  FAILED  │
   └────────┘  └──────────┘
                  │
                  ▼
            ┌──────────┐
            │ RETRYING │  (max 3 retries, exponential backoff: 60s, 300s, 900s)
            └──────────┘
```

### 4.3 Task details

#### `extract_events(week_start: str) -> pd.DataFrame`

- **Tags:** `"service": "reporting"`, `"task": "extract"`
- **Cache:** `cache_key_fn=week_start_cache_key`, `cache_expiration=3600` (events don't change for past weeks)
- **Error handling:** Retry on `OperationalError` (DB connection lost), max 2 retries
- **Output schema:** columns `warehouse`, `client_id`, `week_start`, `event_type`, `quantity`

#### `transform_to_kpis(raw_df: pd.DataFrame) -> pd.DataFrame`

- **Tags:** `"service": "reporting"`, `"task": "transform"`
- **Cache:** None (pure computation — fast to re-run)
- **Error handling:** Validate input columns exist; raise `ValueError` with explicit message if schema mismatch
- **Output schema:** columns matching destination table (without `id` or `computed_at`)

#### `load_to_reporting(kpi_df: pd.DataFrame) -> int`

- **Tags:** `"service": "reporting"`, `"task": "load"`
- **Cache:** None (must execute to persist data)
- **Error handling:** Wrap in transaction; rollback on any SQL error
- **Returns:** row count upserted

#### `record_watermark(week_start: str, status: str) -> None`

- **Tags:** `"service": "reporting"`, `"task": "watermark"`
- **Error handling:** Independent of main pipeline — failure does not rollback the upsert (watermark is advisory)

### 4.4 Scheduling

```python
from prefect import flow
from prefect.deployments import Deployment

@flow(cron="0 1 * * 1",  # Every Monday at 01:00 UTC
      name="weekly_client_performance",
      description="Compute weekly warehouse × client KPIs")
def weekly_client_performance_pipeline():
    ...
```

### 4.5 Cross-cutting concerns

| Concern | Implementation |
|---------|---------------|
| Logging | Prefect automatic logging per task; plus structured log lines with `week_start` and row counts |
| Alerting | On `FAILED` state after 3 retries, emit notification (email/PagerDuty/webhook) via Prefect hooks |
| Concurrency | `max_retries=3`, no concurrent runs (cron is non-overlapping); use `FlowRun` concurrency limit if needed |
| Parameters | `week_start` defaults to `(now - 7 days).start_of_week`; override for manual backfill |

---

## Phase 5 — Application Integration

### 5.1 New module: `services/reporting/`

Create a new Python module alongside `services/telemetry/`:

```
services/
├── telemetry/
│   ├── __init__.py
│   ├── analysis.py
│   └── ...
├── reporting/
│   ├── __init__.py
│   ├── router.py         # FastAPI router
│   ├── pipeline.py       # Pipeline orchestration (Phase 2 logic)
│   └── models.py         # Pydantic request/response models
└── main.py               # Register new router here
```

### 5.2 API endpoint

**`GET /api/reporting/performance`**

Accepts optional `week_start` query parameter (ISO date string, e.g. `2026-07-13`). Defaults to the most recent computed week.

```json
{
  "week_start": "2026-07-13",
  "computed_at": "2026-07-20T01:05:00Z",
  "entries": [
    {
      "warehouse": "los_angeles",
      "client_id": "fashion-co",
      "inbound_units_count": 4200,
      "outbound_orders_count": 980,
      "stockout_events_count": 3,
      "discrepancy_events_count": 2,
      "discrepancy_rate": 0.002
    }
  ]
}
```

**Implementation approach:**

```python
from fastapi import APIRouter, Query
from services.database import get_session  # existing SQLAlchemy session

router = APIRouter(prefix="/api/reporting", tags=["reporting"])

@router.get("/performance")
def get_performance(
    week_start: str | None = Query(None, description="ISO date (Monday)")
):
    """Return weekly KPI data for warehouse × client performance."""
    ...
```

### 5.3 Supporting endpoints

Each endpoint imports its pipeline function from `services.reporting.pipeline` (the module that implements the design from `data/pipelines/PIPELINE_DESIGN.md`):

| Endpoint | Imports from `services.reporting.pipeline` |
|----------|------------------------------------------|
| `GET /api/reporting/performance` | `compute_weekly_kpis(week_start: str) -> list[dict]` |
| `GET /api/reporting/pipeline-runs/latest` | `get_latest_watermark() -> dict` |
| `POST /api/reporting/pipeline-runs` | `run_pipeline(week_start: str) -> dict` |

**`GET /api/reporting/pipeline-runs/latest`** — Returns the most recent watermark entry (calls `get_latest_watermark()`):

```json
{
  "pipeline_name": "weekly_client_performance",
  "last_completed_week": "2026-07-13",
  "last_run_at": "2026-07-20T01:03:22Z",
  "status": "success"
}
```

**`POST /api/reporting/pipeline-runs`** — Triggers a manual pipeline run (calls `run_pipeline(week_start)` from `services.reporting.pipeline`):

```json
{
  "week_start": "2026-07-13",
  "status": "triggered"
}
```

### 5.4 Registration in `services/main.py`

```python
from services.reporting.router import router as reporting_router

app.include_router(reporting_router)
```

The existing pattern (all routers registered in `services/main.py`) is preserved.

### 5.5 Module dependencies

| Dependency | Used for | Already available? |
|-----------|----------|-------------------|
| `services.telemetry_storage._connect` | PostgreSQL connection | ✅ Yes |
| `psycopg2` | Bulk upsert | ✅ Yes |
| `pandas` | Vectorised aggregation | ✅ Yes (added in Phase 4) |
| `psycopg2.extras.execute_values` | Bulk upsert | ✅ Yes |
| `prefect` | Flow orchestration | ❌ Part 2 (install) |
| `datetime` / `time` | Date math, timing | ✅ Standard library |

---

## Appendix A — Alternative: Pure SQL aggregation

For environments where Pandas is unavailable, the entire transform can be expressed as a single SQL query:

```sql
WITH filtered AS (
  SELECT
    tags->>'warehouse'                          AS warehouse,
    tags->>'client_id'                          AS client_id,
    DATE_TRUNC('week', timestamp::date)::date   AS week_start,
    event_type,
    COALESCE((tags->>'quantity')::integer, 0)   AS quantity
  FROM telemetry_events
  WHERE event_type IN ('inbound_order_created','outbound_order_created',
                       'stock_threshold_triggered','inventory_discrepancy_detected')
    AND timestamp >= %(start)s
    AND timestamp <  %(end)s
),
agg AS (
  SELECT
    warehouse,
    client_id,
    week_start,
    COALESCE(SUM(quantity) FILTER (WHERE event_type = 'inbound_order_created'), 0)
      AS inbound_units_count,
    COUNT(*) FILTER (WHERE event_type = 'outbound_order_created')
      AS outbound_orders_count,
    COUNT(*) FILTER (WHERE event_type = 'stock_threshold_triggered')
      AS stockout_events_count,
    COUNT(*) FILTER (WHERE event_type = 'inventory_discrepancy_detected')
      AS discrepancy_events_count
  FROM filtered
  GROUP BY warehouse, client_id, week_start
)
SELECT *,
  CASE WHEN outbound_orders_count > 0
       THEN ROUND(discrepancy_events_count::numeric / outbound_orders_count, 4)
       ELSE 0
  END AS discrepancy_rate
FROM agg
ORDER BY week_start DESC, warehouse, client_id;
```

This single-query approach is suitable for a **materialised view** or **PostgreSQL function** but is kept as an alternative because:

- It is harder to test in isolation (cannot inspect intermediate DataFrames).
- Pandas with `.groupby().agg()` on separate filtered views is more readable for team maintenance.
- The Pandas approach allows inline validation (e.g., assert no unknown event types leak through).

## Appendix B — KPI-to-event traceability matrix

| KPI | Source event | Aggregation function | JSONB path |
|-----|-------------|---------------------|------------|
| Inbound Volume | `inbound_order_created` | `SUM(tags->>'quantity')` | `tags->>'quantity'` |
| Outbound Throughput | `outbound_order_created` | `COUNT(*)` | — |
| Stockout Frequency | `stock_threshold_triggered` | `COUNT(*)` | — |
| Discrepancy Rate (numerator) | `inventory_discrepancy_detected` | `COUNT(*)` | — |
| Discrepancy Rate (denominator) | `outbound_order_created` | `COUNT(*)` | — |

## Appendix C — Pipeline run state diagram (watermark transitions)

```
                           ┌─────────────────┐
                           │  IDLE            │
                           │  (awaiting cron) │
                           └────────┬────────┘
                                    │ cron fires
                                    ▼
               ┌─────────────────────────────┐
               │  EXTRACTING                  │
               │  watermark: last_run_at      │
               └────────┬────────────────────┘
                        │ success
                        ▼
               ┌─────────────────────────────┐
               │  TRANSFORMING                │
               │  (pure Pandas computation)   │
               └────────┬────────────────────┘
                        │ success
                        ▼
               ┌─────────────────────────────┐
               │  LOADING                     │
               │  (upsert into reporting)     │
               └────────┬────────────────────┘
                        │ success
                        ▼
               ┌─────────────────────────────┐
               │  WATERMARKING                │
               │  UPDATE pipeline_watermark   │
               │  SET status = 'success'     │
               └────────┬────────────────────┘
                        │ done
                        ▼
               ┌─────────────────┐
               │  IDLE            │
               │  (wait 1 week)   │
               └─────────────────┘
          Any step fails ⬇
               ┌─────────────────────────────┐
               │  RETRY (max 3)               │
               │  exponential backoff         │
               │  if exhausted:               │
               │  watermark SET status =      │
               │  'failed'                    │
               └─────────────────────────────┘
```
## Phase 6 — Pipeline Enhancement: Subflows, Pure Functions & Dashboard

### 6.1 Motivation

After Phase 5, the pipeline worked end-to-end but had two weaknesses:

1. **Monolithic flow** — `weekly_client_performance_pipeline` called all four tasks in one flat sequence, making it impossible to observe or retry sub-stages independently in the Prefect UI.
2. **Logic intertwined with orchestration** — KPI computation lived inside `transform_to_kpis` as a `@task`, making it difficult to unit-test without spinning up a Prefect runner.

Phase 6 refactors the pipeline into **subflows**, extracts pure **testable functions**, and adds a **business dashboard** to visualise results.

### 6.2 Subflow Architecture

```
weekly_client_performance_pipeline          (@flow / main entry)
│
├─ extract_weekly_events(week_start)        (@flow / subflow)
│   └─ extract_events(week_start)          (@task)
│
├─ compute_warehouse_client_kpis(raw_df)    (@flow / subflow)
│   └─ transform_to_kpis(raw_df)           (@task)
│       └─ (calls pure functions from kpi_functions.py)
│
└─ upsert_performance_report(kpi_df)        (@flow / subflow)
    ├─ load_to_reporting(kpi_df)           (@task)
    └─ record_watermark(week_start, status) (@task, optional, return_state=True)
```

Each subflow:
- Has its own `@flow` decorator with a descriptive `name` and `description`.
- Can be invoked independently for monitoring or ad-hoc debugging.
- Appears as a separate node in the Prefect UI run graph.
- The main flow still exports the three public symbols expected by `services/reporting/router.py`: `compute_weekly_kpis`, `get_latest_watermark`, `run_pipeline`.

### 6.3 Pure KPI Functions

Extracted into `data/process/kpi_functions.py` for testability without Prefect:

| Function | Input | Output |
|---|---|---|
| `compute_inbound_volume(events)` | Raw events DataFrame | `(warehouse, client_id, week_start, inbound_units_count)` |
| `compute_outbound_throughput(events)` | Raw events DataFrame | `(warehouse, client_id, week_start, outbound_orders_count)` |
| `compute_stockout_frequency(events)` | Raw events DataFrame | `(warehouse, client_id, week_start, stockout_events_count)` |
| `compute_discrepancy_frequency(events)` | Raw events DataFrame | `(warehouse, client_id, week_start, discrepancy_events_count)` |
| `compute_discrepancy_rate(discrepancies, outbounds)` | Two aggregated DataFrames | Merged with `discrepancy_rate` column |
| `aggregate_weekly_kpis(events)` | Raw events DataFrame | Full KPI table (all metrics joined) |
| `_validate_columns(df, required)` | DataFrame + set of columns | Raises `ValueError` if missing |
| `_validate_not_null(series)` | Pandas Series | Raises `ValueError` if any null |

Design decisions:
- All functions are **pure** — no I/O, no side effects, no database calls.
- `pd.to_numeric(errors="coerce")` is used to handle non-numeric quantities defensively.
- `compute_discrepancy_rate` handles the edge case of zero outbound orders gracefully.
- Functions operate on `GROUP_COLS = ["warehouse", "client_id", "week_start"]`.

### 6.4 Test Suite

Location: `tests/pipelines/test_pipeline.py`  
Test framework: `pytest`  
Total tests: **21** (all passing)

| Test class | Tests | What it validates |
|---|---|---|
| `TestComputeInboundVolume` | 3 | Sums quantities correctly; empty events; missing column |
| `TestComputeOutboundThroughput` | 3 | Counts outbound events; Zaragoza=3; empty events |
| `TestComputeStockoutFrequency` | 3 | Counts stockout triggers; GlowLab=2; Zaragoza=0 |
| `TestComputeDiscrepancyFrequency` | 1 | Counts discrepancy events |
| `TestComputeDiscrepancyRate` | 2 | Known rate matches CONTEXT_BRIEFING; zero outbound |
| `TestAggregateWeeklyKpis` | 6 | Shape & counts; Fashion Co KPIs (350/2/1/1/0.5); Soundwave; GlowLab; empty events; null handling |
| `TestDefensiveBehaviour` | 3 | Null warehouse; string quantity; unknown event_type |

Key test data assertions (from `CONTEXT_BRIEFING.md`):
- **Fashion Co**: 350 inbound units, 2 outbound orders, 1 stockout, 1 discrepancy, 0.5 rate
- **Zaragoza outbound**: 3 orders
- **GlowLab stockouts**: 2 events

### 6.5 Business Dashboard

New files:
- `uis/backoffice/WeeklyReportingDashboard.tsx` — React component
- `uis/backoffice/app/uis/backoffice/reporting/page.tsx` — Next.js route

The dashboard provides:
- **Date picker** to select an ISO week (Monday)
- **Query button** to fetch KPI data from `GET /api/reporting/weekly-warehouse-client-performance`
- **Run Pipeline Now** button to trigger `POST /api/reporting/pipeline-runs`
- **Last pipeline run info** from `GET /api/reporting/pipeline-runs/latest`
- **Summary KPI cards**: Total Inbound, Outbound, Stockouts, Discrepancies, Avg Discrepancy Rate, Warehouse×Client combos
- **Detail table** with per-warehouse-per-client breakdown, including colour-coded discrepancy rate (green < 2%, amber 2-5%, red > 5%)
- **Empty state** when no data exists
- **Error display** for API failures
- Navigation link added to `BackofficeHome.tsx` action bar

### 6.6 Design Decisions

| Decision | Rationale |
|---|---|
| Subflows instead of flat tasks | Independent observability; each subflow appears in Prefect UI |
| Pure functions in separate module | Unit-testable without Prefect or database |
| Watermark uses `return_state=True` | Watermark failure never fails the main pipeline |
| `watermark_state` null-guarded | When no PostgreSQL DSN, task returns None gracefully |
| Dashboard calls API via `fetchJson` | Consistent with existing SupplierDirectory pattern |
| KPI cards use `borderLeft` colour | Quick visual scan of metric types |
| `pd.to_numeric(errors="coerce")` | Defensive against non-numeric data in production |

