# LangGraph Agent — Architecture

## Overview

The TrackFlow LangGraph agent routes user questions through a **directed graph
with conditional edges**.  Each node is a Python function that receives and
mutates an `AgentState` TypedDict.  The graph is compiled with
`InMemorySaver` (LangGraph's real checkpointer), then invoked via FastAPI
(`POST /api/agent/query`).

## Graph topology

```
receive_validate
      │
      ▼
route_classify  ──────►  reject_write_intent ────► assemble_final ──► [done]
      │                       │
      │  (write_intent) ──────┘
      │
      │  (rag)  ──► retrieve_context ──► generate_answer ──► assemble_final ──► [done]
      │                │                      │
      │                │  (empty chunks) ─────▼
      │                └──────────► fallback ──► assemble_final ──► [done]
      │
      │  (ticket) ──► lookup_incident ──► retrieve_context ──► generate_answer ──► ...
      │                  │
      │    (found.both) ─┘
      │                  │
      │    (else) ───────► assemble_final ──► [done]
      │
      │  (inventory) ──► lookup_inventory ──► assemble_final ──► [done]
      │
      └── (unknown) ────► fallback ──► assemble_final ──► [done]
```

### Nodes

| Node | Function | Purpose |
|---|---|---|
| `receive_validate` | `receive_validate(state)` | Starts trace run; rejects blank questions |
| `route_classify` | `classify_question(state)` | Keyword classification → `write_intent`, `rag`, `ticket`, `inventory`, `both`, `unknown` |
| `reject_write_intent` | `reject_write_intent(state)` | Returns hard-coded read-only message; preserves existing answer |
| `lookup_incident` | `lookup_incident(state)` | Bounded 5 s call to TinyDB; returns `IncidentLookupResponse` or None |
| `lookup_inventory` | `lookup_inventory(state)` | Queries SQLModel for SKU/stock data |
| `retrieve_context` | `retrieve_context(state)` | Calls `data.process.rag.retrieve` → Qdrant cosine search |
| `generate_answer` | `generate_answer(state)` | Calls `data.pipelines.rag.generate_answer` → LLM with guardrails |
| `fallback` | `fallback(state)` | Sets polite "cannot handle" message |
| `assemble_final` | `assemble_final(state)` | Combines contributions; preserves existing answer; calls `_finish_run` |

### Conditional edges

| Source | Router fn | Destinations |
|---|---|---|
| `route_classify` | `_classify_router(state)` | `reject_write_intent` (write_intent), `lookup_incident` (ticket), `lookup_incident` (both), `retrieve_context` (rag), `lookup_inventory` (inventory), `fallback` (unknown) |
| `lookup_incident` | `_after_incident_router(state)` | `retrieve_context` (both classification), `assemble_final` (else) |
| `retrieve_context` | `_retrieve_router(state)` | `generate_answer` (has chunks), `fallback` (empty) |

## State schema

| Field | Type | Set by |
|---|---|---|
| `question` | `str` | caller |
| `classification` | `str \| None` | `classify_question` |
| `error` | `str \| None` | various nodes on failure |
| `retrieved_chunks` | `list[dict]` | `retrieve_context` |
| `generated_answer` | `str \| None` | `generate_answer` |
| `incident_result` | `IncidentLookupResponse \| None` | `lookup_incident` |
| `inventory_result` | `list[dict]` | `lookup_inventory` |
| `answer` | `str \| None` | `assemble_final` (or `fallback`/`reject_write_intent`) |
| `run_id` | `str \| None` | `receive_validate` |

## Agent tools

| Tool | Input contract | Output contract | Backend | Timeout |
|---|---|---|---|---|
| `lookup_incident_by_id` | `IncidentLookupInput.incident_id: str` | `IncidentLookupResponse \| None` | TinyDB (`services/incidents/manager_data.py`) | 5 s (configurable via `timeout=`) |
| `retrieve` | `query: str` | `list[RetrievedChunk]` | Qdrant (`trackflow_knowledge` collection) | Infinite (caller timeout) |
| `generate_answer` | `question, chunks, provider` | `str` with guardrails | Any `GenerationProvider` | per-provider |

### Incident tool bounds

The incident tool (`services/agent/tools/incident.py`) uses a **module-level**
`ThreadPoolExecutor(max_workers=4)` instead of `with ThreadPoolExecutor(...)`.
This avoids the `shutdown(wait=True)` deadlock that would otherwise block the
caller after a timeout.  On timeout:

1. `future.result(timeout=...)` raises `TimeoutError`
2. `future.cancel()` cancels the hung future
3. `IncidentToolError` is raised immediately (no wait for worker to finish)

## Trace store

| Table | Columns | Purpose |
|---|---|---|
| `runs` | `run_id, question, classification, answer, outcome, started_at, finished_at` | Per-invocation record |
| `nodes` | `id, run_id, node_name, started_at, finished_at, status, details` | Per-node execution log |

- Backend: SQLite at `services/agent/traces/agent_traces.sqlite` (WAL mode).
- Written by `_start_run()` / `_trace_node()` / `_finish_run()` helpers.
- Every invocation persists a trace row, even blank questions and write-intent rejections.

## Classification keywords

| Label | Trigger keywords |
|---|---|
| `write_intent` | create, update, delete, remove, modify, change, close, resolve, cancel, edit, add, new |
| `rag` | return, policy, sla, delivery, storage, pricing, carrier, cost, charge, fee, window, coverage |
| `ticket` | incident, ticket, issue, problem, complaint, trf-, tracking, parcel, lost, damage, delayed |
| `inventory` | inventory, stock, product, SKU, availability, product, item count, warehouse, bin |
| `both` | Both `rag` AND `ticket` keywords present |
| `unknown` | None of the above |

Priority order: write_intent > both > rag > ticket > inventory > unknown.

## Generation guardrails

The `generate_answer` node calls `data.pipelines.rag.generate_answer`, which
appends safety-critical disclaimers when the relevant source was retrieved:

- **SLA / high-demand dates**: "does not guarantee delivery SLA"
- **International returns**: "require manual handling"
- **Storage discounts**: "requires approval from Miguel Torres"
- **Carrier exceptions**: "requires approval from Carlos Vega"

These guardrails are identical to those in `services/knowledge_query.py`.

## FastAPI endpoint

- Route: `POST /api/agent/query`
- Body: `{"question": str}`
- Response: `{"question", "classification", "answer", "run_id", "error"}`
- Checkpointer: `InMemorySaver()` (LangGraph 1.2.20)
- Thread ID: `uuid4()` (new per request)
- Compile failure handling: caught, logged, 503 returned

## Offline replay eval

Live traces (RAG, incident, both) are captured to `data/eval/live-traces/*.json`
by ``scripts/capture_live_agent_traces.py``, which loads ``backend/.env``
privately (``load_dotenv("backend/.env", override=False)``, no secrets printed).

Offline replay tests in ``tests/pipelines/test_offline_replay.py`` read the saved
JSON traces and assert known facts **without** compiling the graph, calling
Qdrant, TinyDB, or the LLM:

| Test class | Scope | Key assertions |
|---|---|---|
| ``TestOfflineTraceStructural`` | All traces | Core keys present, run_id valid, no errors |
| ``TestOfflineRagOnly`` | ``rag.json`` | ≥1 chunk with payload.text, citation marker, no incident/inventory keys |
| ``TestOfflineIncidentOnly`` | ``incident.json`` | ``incident_result`` with all 9 fields, known ID, status=open, category=lost_parcel |
| ``TestOfflineBoth`` | ``both.json`` | Both chunks and incident_result present, chunk text preserved |
| ``TestOfflineToolContract`` | incident + both | ``incident_result`` matches ``IncidentLookupResponse`` TypedDict contract |

Workflow::

    # 1. Capture live traces (requires Qdrant + LLM credentials in backend/.env)
    uv run --env-file backend/.env python scripts/capture_live_agent_traces.py

    # 2. Run offline replay (no live services needed)
    .venv/bin/python -m pytest tests/pipelines/test_offline_replay.py -v

    # 3. Run full agent test suite
    .venv/bin/python -m pytest tests/pipelines/test_agent_graph.py -v
