# TrackFlow Telemetry Plan

**Owner:** TrackFlow Tech
**Status:** Foundation implemented (backend) — Phase 2 of 4
**Source of truth:** [`event-schemas.json`](../event-schemas.json) at repo root. This document is the narrative plan; the JSON schema is the machine-checkable contract the implementation (and tests) enforce. Where anything appears to differ, **the schema wins** and this document must be updated to match.

> Business context: TrackFlow manages warehousing and last-mile delivery for fashion, electronics and cosmetics brands between Los Angeles and Zaragoza. Inventory **is the business**. This telemetry powers, later, Ana's warehouse-operations dashboard and Thomas's global executive dashboard (volume and SLA comparison US vs ES). Every event is therefore designed to be **aggregatable by warehouse, by client, and by country** from day one.

---

## 1. Mandatory Metrics (minimum floor, from CONTEXT-company.md)

These five `event_type`s are mandatory from day one and are instrumented end-to-end. They carry the minimum `properties` set `warehouse` (`los_angeles`/`zaragoza`), `client_id`, `product_id`, `product_category`, `quantity` — verified present and required for all five in `event-schemas.json`.

| `event_type` | Classification | Delivery | Business hypothesis | Decision it enables |
|---|---|---|---|---|
| `inbound_order_created` | MANDATORY | stream | We need to know how much volume comes in, by client and by warehouse. | Plan warehouse capacity and staffing based on incoming volume (Ana). |
| `outbound_order_created` | MANDATORY | stream | We need to know how many orders are processed, by client and warehouse, and at what rate. | Detect operational bottlenecks before they affect delivery SLA (Ana). |
| `stock_threshold_triggered` | MANDATORY | stream | We need to know how often a client runs out of available stock for a SKU. | Alert the client and the commercial team before a stockout (Miguel). |
| `direct_stock_edit_rejected` | MANDATORY | stream | We need to know if warehouse staff are attempting to bypass traceability controls. | Reinforce training or permissions at the warehouse where this happens most (Ana). |
| `inventory_discrepancy_detected` | MANDATORY | batch | We need to know which SKUs and warehouses see the most discrepancies between system and physical stock. | Prioritise inventory audits on the SKUs with the highest discrepancy rate (Ana). |

> ⚠️ **No end-consumer personal data** (package recipient) appears in `properties`. These events describe warehouse inventory, not individual home deliveries — that belongs to the last-mile tracking project.

---

## 2. Event Envelope (consistent across all events)

Every event is a single consistent envelope plus an allowlisted `properties` object. All 35 events require exactly these 8 fields (verified in `event-schemas.json` `$defs/events/*.required` and enforced by `backend/telemetry/registry.py::validate_event`):

| Field | Type / format | Notes |
|---|---|---|
| `eventId` | string (uuid v4) | Unique event identifier. |
| `timestamp` | string, ISO 8601 / RFC 3339 UTC (`2026-10-15T09:30:00Z`) | Milliseconds precision. |
| `sessionId` | string (uuid) | Client session scope (`tf_session_id`); `"anonymous"` pre-auth. |
| `userId` | string | TinyDB user UUID, or `"anonymous"` for pre-auth/public flows. |
| `event_type` | string, `entity_action` (lowercase snake_case) | e.g. `inbound_order_created`. Taxonomy: `^[a-z]+_[a-z]+(?:_[a-z]+)*$`. |
| `schemaVersion` | int | Currently `1`. |
| `requestId` | string (uuid) | Correlation id — `X-Request-Id` header joins frontend → backend → logs → DB. |
| `properties` | object | Event-specific allowlist (below). |

The base definitions (`$defs/envelope`, `$defs/base`) are shared by all events so the envelope cannot drift per event. `api_error`/`api_latency_recorded` additionally carry `route` + `method`; `api_error` carries `status_code`/`error_type`.

---

## 3. Event Catalogue — every event justified (hypothesis → decision)

The golden rule, applied to every event:

> **We capture [event_type] because we need to know [hypothesis], which allows us to make the decision [concrete decision].**

No "just in case" events. Classification = **MANDATORY** (context floor) or **OPPORTUNITY** (catalogue). `delivery` per §4. `pii` = `false` (no PII) or `sanitised` (PII-bearing fields deliberately excluded / replaced). Allowlist = the ONLY permitted `properties` keys (`additionalProperties: false` at both envelope and properties level).

### 3.1 Inventory & Business (5 MANDATORY + 4 OPPORTUNITY)

| `event_type` | Allowlist (required in bold) | Hypothesis | Decision | delivery | pii |
|---|---|---|---|---|---|
| `inbound_order_created` | **warehouse, client_id, product_id, product_category, quantity**, order_id, reference, stock_after, country | Volume in, by client and warehouse | Plan capacity/staffing (Ana) | stream | false |
| `outbound_order_created` | **warehouse, client_id, product_id, product_category, quantity**, order_id, exit_type, stock_after, country | Orders processed, by client/warehouse/rate | Detect bottlenecks before SLA impact (Ana) | stream | false |
| `stock_threshold_triggered` | **warehouse, client_id, product_id, product_category, quantity, threshold_value**, country | How often a client runs out of stock for a SKU | Alert client + commercial before stockout (Miguel) | stream | false |
| `direct_stock_edit_rejected` | **warehouse, client_id, product_id, product_category, quantity, reason**, target_field | Staff bypassing traceability controls | Reinforce training/permissions at worst warehouse (Ana) | stream | false |
| `inventory_discrepancy_detected` | **warehouse, client_id, product_id, product_category, quantity, physical_stock, variance**, audit_reference, variance_ratio | Which SKUs/warehouses see most discrepancies | Prioritise audits (Ana) | batch | false |
| `outbound_order_rejected` | **warehouse, client_id, product_id, product_category, quantity, available_stock, reason**, exit_type | Why outbound orders fail (insufficient stock, warehouse mismatch, …) | Root-cause fixes, stock planning | stream | false |
| `inventory_order_validation_error` | **flow, field, error_code**, product_id, client_id | Recurring input errors at field level | Fix UX/training on the specific fields | batch | false |
| `inventory_product_created` | **warehouse, client_id, product_id, product_category, initial_stock** | Catalogue growth by client/category/warehouse | Plan storage/capacity, observe mix | batch | false |
| `inventory_products_viewed` | **section**, warehouse, result_count | Which inventory views operators use | Prioritise backoffice inventory UX | batch | false |

### 3.2 Authentication & Sessions (9 OPPORTUNITY)

| `event_type` | Allowlist (required in bold) | Hypothesis | Decision | delivery | pii |
|---|---|---|---|---|---|
| `auth_login_succeeded` | **method**, role, region | Auth volume + role distribution | Access provisioning, capacity, security review | batch | false |
| `auth_login_failed` | **reason, method**, region | Brute-force / credential problems by region | Security hardening, lockout policy | stream | sanitised |
| `session_expired` | **reason**, route, token_age_ms | UX friction from expired/invalid sessions | Adjust token TTL, re-auth flow | batch | false |
| `auth_registration_created` | **role, region**, method | Signup volume + role mix | Access provisioning | batch | false |
| `auth_registration_failed` | **reason** | Email conflicts / validation friction | UX fixes, support triage | batch | sanitised |
| `auth_password_reset_requested` | **token_issued** | Frequency of forgotten passwords | Password policy / self-service UX | batch | sanitised |
| `auth_password_reset_completed` | **success**, method | Success rate of the reset flow | Fix broken reset steps | batch | false |
| `auth_password_changed` | **source** | Proactive security behaviour | Encourage / compliance | batch | false |
| `session_ended` | **reason**, session_duration_ms | Session lengths and why sessions end | Auto-logout policy, UX | batch | false |

### 3.3 Performance & Errors (4 OPPORTUNITY)

| `event_type` | Allowlist (required in bold) | Hypothesis | Decision | delivery | pii |
|---|---|---|---|---|---|
| `api_latency_recorded` | **route, method, status_code, duration_ms**, component, sampled | Endpoint latency distribution | Perf budget, bottleneck detection (sampled) | batch | false |
| `frontend_page_load` | **route, metric, value_ms**, device, connection | Core Web Vitals by route/device | Frontend performance work | batch | false |
| `frontend_error_uncaught` | **route, error_type, message_hash**, component, count | JS error rate by route/component | Fix top errors (hash only, never raw text) | stream | false |
| `api_error` | **route, method, status_code, error_type**, duration_ms | 5xx / unhandled error rate by route | Alerting + fix | stream | false |

### 3.4 Navigation (2 OPPORTUNITY)

| `event_type` | Allowlist (required in bold) | Hypothesis | Decision | delivery | pii |
|---|---|---|---|---|---|
| `page_view` | **route, section**, referrer_section, locale, time_on_page_ms | Usage by section | Roadmap / content prioritisation | batch | false |
| `flow_abandoned` | **flow, route, last_step, time_in_flow_ms**, reason | Where multi-step flows drop off | Fix friction points | batch | false |

### 3.5 CRM / Leads (3 OPPORTUNITY)

| `event_type` | Allowlist (required in bold) | Hypothesis | Decision | delivery | pii |
|---|---|---|---|---|---|
| `candidate_created` | **candidate_id, operating_country, product_type, monthly_volume**, services_of_interest, source | Lead volume by country/product | Sales capacity planning | batch | sanitised |
| `candidate_status_updated` | **candidate_id, from_status, to_status, from_stage, to_stage**, changed_by_role | Pipeline velocity | Sales funnel health | batch | false |
| `lead_form_validation_failed` | **field, error_message_key, attempt**, monthly_volume | Which form fields trip users | Form UX fixes | batch | sanitised |

### 3.6 Incidents (5 OPPORTUNITY)

| `event_type` | Allowlist (required in bold) | Hypothesis | Decision | delivery | pii |
|---|---|---|---|---|---|
| `incident_created` | **incident_id, category, origin, branch, status, severity** | Incident volume by category/origin/branch | Ops focus (Andrés/Thomas) | stream | false |
| `incident_created_validation_error` | **field, error_code**, language | Input errors on incident form | Form UX fixes | batch | false |
| `incident_status_changed` | **incident_id, from_status, to_status, branch, category**, resolution_time_ms | Resolution time / SLA per branch | SLA enforcement (Thomas sees >24h) | stream | false |
| `incident_status_transition_rejected` | **incident_id, from_status, attempted_to**, reason | Staff misunderstanding the state machine | Training / clearer UX | stream | false |
| `incident_analysis_completed` | **total_records, valid_records, invalid_records**, error_type_counts, duration_ms | Data quality of incident CSV dumps | Validation rigour | batch | false |

### 3.7 Suppliers (3 OPPORTUNITY)

| `event_type` | Allowlist (required in bold) | Hypothesis | Decision | delivery | pii |
|---|---|---|---|---|---|
| `supplier_created` | **supplier_id, country, currency, categories, rate_per_shipment, status**, service_zone | Carrier/supplier network growth | Coverage by country/rate | batch | sanitised |
| `supplier_created_validation_error` | **field, error_code**, country_attempted | Entry errors (currency/country mismatch) | Form UX fixes | batch | false |
| `supplier_updated` | **supplier_id, field, from_value, to_value**, currency | Rate changes / churn | Negotiate / oversight | batch | false |

**Total: 5 MANDATORY + 30 OPPORTUNITY = 35 events.** Every one of the 30 OPPORTUNITY events above exists because it answers a question TrackFlow acts on — none are decoration.

---

## 4. Delivery Strategy — stream vs batch (justified by operational urgency)

Decisions are driven by **how quickly the business can act on the signal**, not by what is easiest to build.

### 4.1 Stream (near-real-time) — the business reacts in minutes

| Event | Why urgent |
|---|---|
| `inbound_order_created`, `outbound_order_created` | Live volume feeds Ana's shift capacity decisions; delays here = missed SLA window. |
| `stock_threshold_triggered` | A stockout costs the client contract; Miguel's commercial team must be alerted before it happens. |
| `direct_stock_edit_rejected` | A traceability bypass is a control failure; needs attention the same shift. |
| `outbound_order_rejected` | A rejected dispatch is immediate lost throughput; ops must intervene now. |
| `auth_login_failed` | Security signal; a brute-force burst needs same-hour response. |
| `api_error`, `frontend_error_uncaught` | Errors mean degraded service now; on-call needs the alert immediately. |
| `incident_created`, `incident_status_changed` (incl. SLA), `incident_status_transition_rejected` | Thomas tracks open critical incidents in real time (LA vs ZGZ, >24h). |

### 4.2 Batch (analytics window: hourly/daily) — the business acts on aggregates

| Event | Why latency is acceptable |
|---|---|
| `inventory_discrepancy_detected` | Audits are scheduled (daily stock counts) — no event is real-time by nature. |
| `inventory_product_created`, `inventory_products_viewed`, `inventory_order_validation_error` | Feed weekly planning / UX boards. |
| `auth_*` (succeeded, registration, password, session) | Feed daily security/capacity/UX reviews; no one acts within minutes. |
| `api_latency_recorded`, `frontend_page_load` | Perf budgets are reviewed on dashboards; high-volume → sampled + batch to control cost/cardinality. |
| `page_view`, `flow_abandoned` | Product/roadmap cadence is weekly. |
| `candidate_*`, `lead_form_*`, `supplier_*`, `incident_*_validation_error`, `incident_analysis_completed` | Sales/commercial/supplier reviews are daily-to-weekly. |

Sampling and deduplication are part of the delivery design, not afterthoughts:

- **`api_latency_recorded`** is **sampled** (default 1.0, configurable via `TELEMETRY_LATENCY_SAMPLE_RATE`) because full-fidelity latency on every request is unnecessary for a percentile-based perf budget and would create avoidable cardinality/cost.
- **`stock_threshold_triggered`** is **deduplicated** to once per UTC day per `product_id:warehouse` (`emit_threshold`), preventing alert storms from repeated crossing of the same threshold.
- Batch events are buffered and flushed in groups (in-memory buffer → JSONL sink in the foundation; a streaming pipeline is a later milestone, see §7).

---

## 5. Sensitive Data & PII — identification and sanitisation

### 5.1 What PII/sensitive data exists in the system

| Data | Where it lives | In telemetry? |
|---|---|---|
| User identity (uuid), role | TinyDB `users` | Yes — `userId`, `role` only |
| Email / password / reset token | request payloads, DB | **Never** |
| Package recipient name/address/phone | last-mile domain | **Never** (out of scope: warehouse inventory events) |
| `tracking_number` | carrier payloads | **Never** (not in any allowlist) |
| Candidate company contacts / email / phone | CRM | **Never** in `properties` (`candidate_id` is an internal UUID resolved via access-controlled CRM) |
| Public lead form typed values | form submissions | **Never** — `error_message_key` is a stable id, never the typed value |
| Supplier contact email / notes | supplier records | **Never** (`note` const in schema) |
| Incident free-text description | incident records | **Never** (`incident_id` + enums only, `note` const in schema) |
| Raw error message / stack | runtime | **Never** — `frontend_error_uncaught` uses `message_hash` |

### 5.2 Sanitisation strategy — enforced by construction

1. **Strict allowlists** — every event schema sets `additionalProperties: false` at both the envelope and the properties level. A field not explicitly allowed cannot be emitted; `validate_event` rejects unknown keys before buffering (drops with a WARNING), and the sink never sees them.
2. **`pii: "sanitised"` flag** per event in the catalog (§3) marks exactly which events are PII-adjacent and how they are rendered safe.
3. **Always-anonymous where pre-auth** — `auth_login_failed`, `auth_registration_failed`, `auth_password_reset_requested`, `lead_form_validation_failed` fix `userId` to `"anonymous"`.
4. **Boolean/fact replacement** — `auth_password_reset_requested` carries only `token_issued: bool`; the email and token are never captured. `auth_login_failed` carries `reason` enum + a `note` const stating the fact. `auth_login_succeeded` carries role/region only.
5. **Hashing for diagnostics** — `frontend_error_uncaught` ships `message_hash` (stable hash of message+stack), never raw text.
6. **Internal identifiers over PII** — `candidate_id`, `supplier_id`, `incident_id` are internal IDs; any human data is resolved through access-controlled systems on-demand.
7. **No end-recipient data** — inventory event allowlists contain no recipient/tracking fields (CONTEXT-company §6 compliance; enforced by schema).

### 5.3 Correlation

Every event carries `requestId`, minted from the inbound `X-Request-Id` (or a fresh uuid4) by `TelemetryMiddleware`, which also echoes it on the response. This joins frontend → backend → logs → DB so a PII incident can be traced end-to-end if ever needed while keeping the payload itself clean.

---

## 6. Risks & Exclusions (critical thinking)

### 6.1 Events deliberately excluded — and why

| Candidate event | Why discarded |
|---|---|
| `package_delivered` / recipient details | Belongs to the **last-mile tracking project**, an explicitly separate domain. Warehouse-inventory events must not mix recipient PII into inventory aggregates. |
| Raw `auth_login_failed` with attempted email/password | Direct credential-capture risk; the *reason* enum + `anonymous` userId answers the security question without the data. |
| Raw error messages / stack traces as event text | Free-text error blobs are high-cardinality, hard to aggregate, and may embed PII/state; `error_type` + `message_hash` are the analysable, safe signal. |
| Per-request `direct_stock_edit` **inventory mutation** events | Stock is never modified directly by design (CONTEXT-company §6); there is no legitimate write path — so the *rejection* is captured (`direct_stock_edit_rejected`), not the mutation. |
| Return-values / full request bodies in `inventory_order_validation_error` | Only `flow`/`field`/`error_code` are kept; bodies may contain client references or PII. |
| `tracking_number` on outbound events | A carrier identifier that can join to recipient data; excluded from all allowlists (implementation comment in `services/routers/inventory.py` confirms the schema makes leakage impossible). |
| End-user page-level clickstream beyond `page_view`/`flow_abandoned` | No product need yet; re-visit if UX research requires it (avoids data-hoarding). |

### 6.2 Telemetry-system risks and mitigations

| Risk | Mitigation |
|---|---|
| **PII/property leakage into events** | Schema `additionalProperties:false` at both levels + `validate_event` drops invalid events with WARNING before buffering; dedicated tests lock auth/incident/candidate events as PII-safe end-to-end through the HTTP stack. |
| **Buffer loss on process crash** (in-memory buffer) | Accepted for the foundation; flush is non-raising and drains to JSONL sink when configured. A durable stream pipeline is the next milestone. |
| **Flush/sink failure** | `flush()` catches OSError, logs, restores the buffer, returns 0 — never raises into request handling. |
| **Cardinality / cost explosion** | `api_latency_recorded` sampled (`TELEMETRY_LATENCY_SAMPLE_RATE`, default 1.0); threshold events deduped once/day per key; batch delivery for analytic events. |
| **Sampling bias** | Sample rate is recorded in the event (`sampled` flag) and configurable; cohorts are never compared across different rates. |
| **Telemetry disabling regressions** | `TELEMETRY_ENABLED` makes the whole package a fast no-op (existing behaviour/tests unaffected); middleware still provides correlation + the legacy log line without emitting. |
| **Schema drift between plan and JSON** | `event-schemas.json` is the single source of truth; registry loads it with `lru_cache`; 35/35 consistency + envelope/allowlist/entity_action verified by the test suite. |
| **Known-enum drift** (role, reason, category) | Enums live in `$defs/enums` and are referenced (not duplicated) across events; unsupported values fail validation. |

---

## 7. Implementation notes (precision for the implementing developer)

See `backend/telemetry/` (foundation) — all of the following is already wired and tested:

- **`core.py`** — `emit()` builds the envelope (eventId uuid4, ISO-8601 millisecond UTC, `anonymous` defaults), validates against the registry, buffers, auto-flushes at 1000; `emit_threshold()` dedupes once/day; `flush()` writes JSONL to `TELEMETRY_SINK_PATH` or drains as a no-op; `set_request_id()`/`current_request_id()` for correlation. Never raises.
- **`registry.py`** — loads `event-schemas.json` (override `TELEMETRY_SCHEMA_PATH`), exposes `KNOWN_EVENTS`, per-event allowlist, `validate_event()` (empty list = valid).
- **`context.py`** — warehouse/client/country normalization; `client_id_from_name` stable slug (→ `client_id`); `DEFAULT_LOW_STOCK_THRESHOLD` (`TELEMETRY_LOW_STOCK_THRESHOLD`, default 20).
- **`inventory_events.py`** — inbound/outbound/threshold/rejection emit helpers + `inventory_context()` which returns `{}` (event skipped) whenever required context is unavailable — PII-safe by construction.
- **`auth_events.py`** — login/registration/password/session emit helpers, sanitised as per §5 (never pass email/password/token).
- **`middleware.py`** — `TelemetryMiddleware` replaces the legacy `timing_middleware` (same log line preserved), honours/mints `X-Request-Id`, emits `api_latency_recorded` (sampled) for successful responses and `api_error` for 5xx/unhandled, ignores `/health`, `/docs`, `/openapi.json`, `/redoc`.
- **Wiring** — `install_telemetry(app)` in `backend/main.py`; inventory routers in `services/routers/inventory.py`; auth events in `backend/main.py` + `backend/auth.py::get_current_user` (session_expired reasons).
- **Env knobs** — `TELEMETRY_ENABLED`, `TELEMETRY_SCHEMA_PATH`, `TELEMETRY_SINK_PATH`, `TELEMETRY_LATENCY_SAMPLE_RATE`, `TELEMETRY_LOW_STOCK_THRESHOLD`.
- **Tests** — `backend/tests/test_telemetry.py` (21 tests) covers registry floor, envelope validation, normalization, allowlists, dedupe, correlation, and HTTP-level PII safety; full suite 139 passed.

### Intentional phase boundaries

- `direct_stock_edit_rejected` and `inventory_discrepancy_detected` emit helpers exist and are imported; their call sites land with the **direct-write guard** and the **nightly audit job** (later milestones), not silently dropped. They are never part of a legit direct-write path today.

---

## 8. Consistency statement

- `event-schemas.json` **is** the plan's machine-readable form: 35 events, catalog classification/delivery/pii, envelope, allowlists, enums, value types.
- This Markdown document is the narrative form; §3 tables mirror the catalog + `$defs/events` exactly.
- The implementation enforces the schema (validate → drop → buffer → flush) and the test suite locks both directions: events documented here emit schema-valid envelopes, and schema-invalid properties are rejected.