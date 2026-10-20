# Phase 3 — Telemetry Storage: Proof & Resubmit Evidence

This document consolidates the evidence for the Phase 3 storage resubmit.

**Feedback addressed:**

> "Solid TrackFlow storage — append-only DDL with indexes, loose batch plus per-event validation, bulk insert with received/stored/rejected, model untouched, no frontend changes on part three, and telemetry pytest green here. However no Supabase or PR proof that rows landed with event_type and tags, and tags keep every properties key without plan allowlist filtering. Add table screenshots and trim properties before insert. Please resubmit."

---

## 1. What changed in this resubmit

### 1.1 Trim properties to the plan allowlist **before insert** ✅

| Location | Change |
|---|---|
| `services/telemetry_storage.py` | New `trim_properties_to_allowlist(event_type, properties)` — drops any `properties` key not in the event's schema allowlist (source of truth: `event-schemas.json` via `backend/telemetry/registry.get_properties_allowlist`). Applied in `_prepare_rows`, so the row tuple handed to `psycopg2.execute_values` already has trimmed `tags`. |
| `services/routers/telemetry.py` | Docstring updated: endpoint remains a **loose** envelope validator (still returns 200 + `{received, stored, rejected}`); the allowlist enforcement now happens at the storage boundary (defence in depth, TELEMETRY_PLAN §5.2.1). No response-contract change → frontend unaffected. |
| `services/tests/test_telemetry_events.py` | +5 tests locking the trimming behaviour (see §3). Existing contract tests unchanged and still green (an out-of-plan property is accepted at the endpoint but stripped before insert). |
| `docs/TELEMETRY_PLAN.md` | §5.2.1 and §7 now document the persist-time allowlist re-filter. |
| `scripts/create_telemetry_table.sql` | Column comment clarifies `tags` holds the **allowlist-trimmed** properties object. |

**What "trim before insert" means in practice:**

- `auth_login_succeeded` with `{"method": "password", "password_raw": "supersecret"}`  
  → persists `tags = {"method": "password"}`. `password_raw` never reaches the DB.
- `inbound_order_created` with `"tracking_number"` (never allowlisted, TELEMETRY_PLAN §6.1)  
  → `tags` omits it.
- Unknown `event_type` → empty allowlist → `tags = {}` (event still stored; the
  `{received, stored, rejected}` contract is preserved).

### 1.2 Proof that rows landed with `event_type` and `tags`

The feedback asked for Supabase/PR proof. The table screenshot itself is captured
**by you** (see §2 for exactly what to screenshot). This repo now ships the script
that makes the proof reproducible and unambiguous:

`scripts/seed_telemetry_proof.py` — seeds deterministic events through the **same
`insert_telemetry_events` path the endpoint uses**, then queries `telemetry_events`
back and prints a table with `event_type`, derived `service`, and the **trimmed**
`tags` JSONB, plus an explicit ✅/❌ trimming verdict.

---

## 2. How to capture the proof (screenshot checklist)

> You said you'll take care of the screenshot — this is the exact checklist so the
> screenshot satisfies the reviewer.

1. **Apply the DDL** in Supabase's SQL editor: `scripts/create_telemetry_table.sql`
   (appended `telemetry_events` with indexes + RLS).
2. **Seed + verify** (run from repo root with your `.venv`):
   ```bash
   TELEMETRY_DATABASE_URL=<supabase-postgres-dsn> \
     .venv/bin/python -m scripts.seed_telemetry_proof
   ```
3. **Screenshot (A) — script output** showing:
   - the header line `PHASE 3 STORAGE PROOF — telemetry_events`,
   - rows for `inbound_order_created`, `outbound_order_created`,
     `stock_threshold_triggered`, `inventory_discrepancy_detected`,
     `auth_login_succeeded`, `page_view`,
   - the final line **`✅ No out-of-plan keys present ... trims correctly.`**
4. **Screenshot (B) — Supabase Table Editor** (`telemetry_events`): sort by
   `timestamp DESC`, show columns `event_type` + `tags`. This is the reviewer's
   "rows landed with event_type and tags" proof.
5. *(Optional, strongest)* **Screenshot (C) — SQL query + result** in Supabase:
   ```sql
   SELECT event_type, service, tags
     FROM telemetry_events
     ORDER BY timestamp DESC
     LIMIT 10;
   ```
   Show that the `tags` cell for `auth_login_succeeded` contains `{"method":
   "password"}` and **no** `password_raw` key (with the other seeded rows).

> ⚠️ Do **not** screenshot a run whose report ends with `❌ LEAK DETECTED` — that
> would mean the DB has stale/leaky rows from before the fix. If that happens,
> delete the earlier rows first:
> ```sql
> DELETE FROM telemetry_events
>  WHERE tags ? 'password_raw' OR tags ? 'tracking_number';
> ```

---

## 3. Tests — allowlist trimming locked in

New tests in `services/tests/test_telemetry_events.py` (all telemetry tests green):

| Test | What it proves |
|---|---|
| `test_trim_properties_to_allowlist_keeps_only_allowlisted_keys` | `auth_login_succeeded` keeps `method`/`region`, drops `password_raw`. |
| `test_trim_properties_keeps_inbound_mandatory_properties` | All 5 mandatory inventory properties survive; `tracking_number` dropped. |
| `test_trim_properties_empty_for_unknown_event_type` | Unknown event → `tags = {}`, event still storable. |
| `test_trim_properties_handles_non_dict` | `None`/non-dict → `{}`, never `None`. |
| `test_prepare_rows_trims_properties_end_to_end` | The exact tuple shape sent to `execute_values` carries trimmed `tags`. |

Existing contract tests (unchanged, still passing):
- `test_telemetry_events_disallowed_property_is_accepted` — out-of-plan property
  is accepted at the endpoint (still `stored = 1`) but trimmed by storage.
- `test_telemetry_events_accepts_valid_batch`, `..._partial_acceptance`,
  `..._partial_persistence`, storage-DSN `RuntimeError` — unchanged.

**Run:**
```bash
.venv/bin/python -m pytest services/tests/test_telemetry_events.py \
  services/tests/test_telemetry_report.py backend/tests/test_telemetry.py -q
# → 49 passed
```

---

## 4. Files touched in this resubmit

| File | Change |
|---|---|
| `services/telemetry_storage.py` | Allowlist trimming before insert (`trim_properties_to_allowlist` + `_prepare_rows`). |
| `services/routers/telemetry.py` | Docstring: storage-boundary trimming, no contract change. |
| `services/tests/test_telemetry_events.py` | +5 trimming tests; module docstring updated. |
| `docs/TELEMETRY_PLAN.md` | §5.2.1 defence-in-depth + §7 storage note. |
| `scripts/create_telemetry_table.sql` | Comment: `tags` = allowlist-trimmed properties. |
| `scripts/seed_telemetry_proof.py` | **New** — seed + verify + screenshot-ready report. |
| `scripts/README.md` / `README.es.md` | Document the proof script. |