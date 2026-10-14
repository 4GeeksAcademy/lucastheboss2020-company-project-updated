# Caching and Performance Report

## Scope and approach

The composed API (`services/main.py`) serves inventory, supplier, and incident endpoints. This report covers all backend and frontend decisions made during this optimization pass, including measured cost, TTL rationale, invalidation strategy, and deliberate non-caching choices.

The local repository contains a persisted incident dataset (`services/incidents/data/incidents-manager.json`, 95 rows, 44,026 bytes at measurement time). Measurements are local microbenchmarks, not production traffic or end-to-end network timings, and were taken with `time.perf_counter()` in a single process.

## Instrumentation

`backend.main` has request timing middleware using `time.perf_counter()`. It logs HTTP method, URL path, response status, and elapsed milliseconds, with a `finally` block so exceptions are also timed. Because `services.main` composes this same app, the middleware covers the unified service API. This is for local diagnostics; it is not a metrics backend and does not by itself establish request frequency in deployment.

## Backend caches (2 endpoints)

### 1. Incident summary (`GET /api/incidents/summary`)

The summary endpoint reads all 95 persisted records, computes group counts across status, category, origin, branch, critical-open figures, and a 24‑hour overdue list with full incident details. It is requested alongside the incident list on the backoffice Manager screen and again on reload/filter changes. It is a global operational view, not a user-specific response.

| Workload (95 records, 300 samples) | Median | Mean | p95 |
| --- | ---: | ---: | ---: |
| Uncached full read + aggregation | 0.802 ms | 0.975 ms | 2.382 ms |
| Warm cache hit including safe `deepcopy` | 0.186 ms | 0.284 ms | 0.516 ms |

**TTL:** 5 seconds. Invalidation via `invalidate_summary_cache()` called synchronously after incident creation, status update, and seed insertion. Explicit-timestamp callers (deterministic tests) bypass the cache.

**Tradeoff:** The 5-second bound means a dashboard user who creates an incident sees the updated count within 5 seconds — fast enough for an operational view without staling during a rapid read burst. Separate Python workers do not share cache state; this is acceptable for a single‑process dev or single‑worker deployment. If multi‑worker parallelism is added, invalidation must go through shared storage or the TTL must be removed.

### 2. Incident list (`GET /api/incidents`)

The list endpoint reads all incidencts and applies client‑supplied filter tuples (`(status, origin, branch, category)`), then sorts descending by `created_at`. The backoffice component fires this on mount and on every filter/reload change with the current filter set, meaning identical filter tuples repeat within short windows.

| Workload (500 samples) | Median | Speedup |
| --- | --: | --: |
| Uncached (95 records, no filter — all) | 0.557 ms | 0.93× (cached copy is slightly slower because of `deepcopy`) |
| Uncached (95 records, status=open filter → 29 rows) | 0.329 ms | 1.84× |
| Warm cache hit — status=open | 0.179 ms | |

The all‑records case shows negligible improvement because reading 95 TinyDB rows and sorting them is already fast; the `deepcopy` overhead of the cached version actually makes it marginally slower. The filtered case (`status=open`, 29 result rows) benefits because the Python‑level filter loop is replaced by a list copy. As the dataset grows (2000+ records) the saved filter+sort cost increases proportionally.

**TTL:** 5 seconds. Invalidation clears the entire filter cache synchronously on any incident write (`create_incident`, `update_incident_status`, `insert_seed_incident`). Cache size is bounded at 128 entries — if more distinct filter tuples appear, stale entries are evicted first, then the oldest live entry if still at the limit.

**Tradeoff:** The same 5‑second staleness bound as the summary, meaning a filter read that was accurate when cached may miss a write that happened 3 seconds ago. This is acceptable because the backoffice UI already fetches on manual interactions. The all‑records case is intentionally cached despite marginal current benefit because (a) it shares the same write‑invalidation paths with no additional complexity and (b) it will win at larger record volumes.

### Shared invalidation pattern

Both caches are cleared by a single `invalidate_summary_cache()` call that resets the summary snapshot and clears the list cache dict. This is called from:
- `create_incident` — after `_incidents.insert`
- `update_incident_status` — after `_incidents.update`
- `insert_seed_incident` — after `_incidents.insert`

Both caches return `deepcopy` results so callers cannot mutate the stored snapshot. All access is protected by the existing `RLock`.

### Deliberate non-caching decisions (backend)

- Inventory, supplier, candidate, and auth endpoints are not cached. The supplier dataset (15 rows, ~0.05 ms median read) and the incident unfiltered list (~0.31 ms) are too fast to justify cache complexity.
- Analysis results (CSV‑derived) are stored in memory by ID lookup and are not repeatedly computed.
- No mutation or file‑download endpoint was cached.
- No Redis was introduced — the in‑process dictionary cache is zero‑dependency and sufficient for a single‑process deployment.

## Frontend optimizations

### Lazy‑loaded components (2)

1. **`BackofficeReports`** — imported dynamically in `BackofficeHome.tsx` via `next/dynamic` with `ssr: false`. This component loads demo fixture data and runs multiple utility‑function aggregations (filtering, grouping, sorting, validation). It renders below the candidate grid and is not needed for the initial viewport. Deferring it keeps the initial JavaScript bundle smaller and lets the main candidate pipeline render first. A loading fallback is shown while the chunk loads.

   **Justification:** The chunk `350.*.js` is ~19 KB (gzipped). Combined with its transitive dependencies from `src/utils/`, lazy loading avoids blocking the main backoffice dashboard interactivity.

2. **`IncidentInvalidRecordDetails`** — imported dynamically in `IncidentAnalyzer.tsx` via `next/dynamic`. This component renders the full list of invalid CSV rows with their individual errors. It is only requested when the user clicks "Expand" on the invalid‑records section. Before this change the inline map was always in the bundle and the DOM was hidden; now the code itself is deferred.

   **Justification:** A CSV analysis can contain hundreds of invalid rows. The component’s bundle is not loaded unless the user chooses to inspect details, saving bandwidth and parse time on the initial analysis view.

### `useMemo` (1)

**`BackofficeReports.tsx`** wraps the entire report computation group in `useMemo(() ⇒ ..., [])`. The dependency array is empty because all input data comes from statically‑imported fixture constants (`DEMO_SERVICES`, `DEMO_LEADS`, `DEMO_FACILITIES`, `DEMO_TEAM_MEMBERS`) that never mutate. The computation includes:

- Six `countLeads*` transformations
- Three collection utilities (`filterBy`, `groupBy`, `sortBy`)
- Two search‑algorithm runs (`linearSearch`, `binarySearch`)
- Four validation‑batch maps (services, leads, facilities, team members)

Without memoization these would recalculate on every render of the BackofficeHome parent whenever the candidate list, search params, or other state changes. The `[]` dependency array is intentionally minimal — these are demo values and should not refresh. If they were replaced with live API data, the dependency array would need the data reference.

### Deliberate non-caching decisions (frontend)

- No additional `useMemo` or `useCallback` was added where profiling evidence does not exist. The existing memoization in `BackofficeReports` was retained and documented.
- Lighthouse‑only numbers were not used to justify further changes; the archived audits show acceptable FCP/LCP/TBT for this project’s scope.

## Verification

- `uv run pytest -q`: **118 passed** (was 115 before the list cache), 3 deprecation warnings.
- `npm run typecheck`: passed.
- Cache tests cover summary expiry, list expiry, mutation invalidation for both caches, safe‑copy isolation, deterministic‑time bypass, and bounded entry count. Fixture setup/teardown clears process‑local cache state.

## Recommendation

Keep the two incident caches with 5‑second TTLs as long as the incident endpoints remain repeatedly read and the bounded staleness is acceptable. Observe the request‑duration logs under representative use before considering wider optimization. If the dataset grows significantly (>10 000 rows), re‑profile the list and summary paths — the `deepcopy` cost for the summary cache grows linearly with the result set.
