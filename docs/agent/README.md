# TrackFlow LangGraph Agent

> LangGraph agent for TrackFlow — RAG pipeline with read-only incident/inventory tools.
>
> - **Python 3.14**, LangGraph 1.2.20, Qdrant 1.20.0, TinyDB
> - Typed tool contracts via `TypedDict` with configurable wall-clock timeouts
> - Offline replay eval from saved live traces (no graph compilation needed)

---

## Prerequisites

| What | Where |
|------|-------|
| Qdrant (vector store) | `docker compose up -d qdrant` → `localhost:6333` |
| Python 3.14 | `.venv/bin/python` (created by `uv sync`) |
| LLM config | `backend/.env` (see below) |
| Database | `DATABASE_URL` in `backend/.env` for inventory tool |

---

## Configuration

All config is read from `backend/.env` by the capture script and FastAPI entry point:

| Key | Required | Purpose |
|-----|----------|---------|
| `QD_HOST` | ✅ | Qdrant host (default `localhost` in code) |
| `QD_PORT` | ✅ | Qdrant HTTP port (default `6333` in code) |
| `RAG_API_BASE_URL` | ✅ | LLM API base (e.g. `https://api.openai.com/v1`) |
| `RAG_API_KEY` | ✅ | LLM API key |
| `RAG_GENERATION_MODEL` | ✅ | LLM model name (e.g. `gpt-4o-mini`) |
| `DATABASE_URL` | ⚠️ | SQLite/Postgres for inventory tool (optional) |
| `NEXT_PUBLIC_TELEMETRY_ENDPOINT` | ❌ | Telemetry endpoint (Next.js build-time only) |

---

## Quick Start

### 1. Start Qdrant

```bash
docker compose up -d qdrant
```

Verify:

```bash
curl -s http://localhost:6333/ | head -c 100
```

### 2. Capture live traces

```bash
uv run --env-file backend/.env .venv/bin/python scripts/capture_live_agent_traces.py
```

This runs the full compiled graph against real Qdrant + LLM + TinyDB and saves
traces to `data/eval/live-traces/{rag,incident,both}.json`.

Output includes node execution order from the SQLite trace store.

### 3. Run offline replay eval (no live services needed)

```bash
.venv/bin/python -m pytest tests/pipelines/test_offline_replay.py -v
```

33 tests — reads saved JSON traces, does **not** compile the graph or call LLM.

### 4. Run all agent graph tests

```bash
.venv/bin/python -m pytest tests/pipelines/test_agent_graph.py -v
```

108 tests — compiles graph, tests node isolation, classification, routing,
bounded tools, trace integration.

### 5. Runtime smoke evaluation script

```bash
uv run --env-file backend/.env .venv/bin/python scripts/evaluate_agent_graph.py
```

This smoke scorecard executes the graph. Use the saved-trace replay command above for evaluations without live services.

---

## Trace Store

The SQLite trace store lives at:

```
services/agent/traces/agent_traces.sqlite
```

**Query recent runs:**

```python
from services.agent.trace import list_runs, get_run

# List last 20 runs
for run in list_runs(limit=20):
    print(run["run_id"], run["classification"], run["outcome"])

# Inspect a specific run
run = get_run(list_runs(limit=1)[0]["run_id"])
print(run["nodes"])  # ordered node execution
```

**Inspect a run from CLI:**

```bash
.venv/bin/python -c "
from services.agent.trace import list_runs, get_run
runs = list_runs(limit=5)
for r in runs:
    print(r['run_id'][:20], r['classification'], r['outcome'])
"
```

---

## Checkpoint Inspect / Pause / Resume

The default `InMemorySaver` stores checkpoints for the life of the Python process. This example pauses before generation, inspects the pending node, then resumes the same run. Run it with the existing backend configuration loaded.

```python
from uuid import uuid4
from langgraph.checkpoint.memory import InMemorySaver
from services.agent.graph import build_agent

graph = build_agent().compile(
    checkpointer=InMemorySaver(),
    interrupt_before=["generate_answer"],
)
config = {"configurable": {"thread_id": str(uuid4())}}
graph.invoke(
    {"question": "What is the return window for a damaged item?"},
    config=config,
)
checkpoint = graph.get_state(config)
assert checkpoint.next == ("generate_answer",)
print(checkpoint.next, len(checkpoint.values["retrieved_chunks"]))

# None resumes the pending work; passing a new question starts a new invocation.
result = graph.invoke(None, config=config)
assert not graph.get_state(config).next
print(result["answer"])
print("Saved checkpoints:", len(list(graph.get_state_history(config))))
```

Verified in the Codespace: the run paused at `generate_answer`, resumed successfully, produced an answer, and retained seven checkpoints. In-memory checkpoints do not survive a process restart; durable semantic traces are stored separately in SQLite.

## Architecture

See [`docs/agent/architecture.md`](architecture.md) for:

- Graph topology ASCII diagram
- Node table (9 nodes, their functions and state effects)
- Conditional edge routing table
- `AgentState` schema
- Tool contracts (incident + inventory)
- Classification keywords
- Guardrails (write-intent rejection)
- Trace store schema
- FastAPI endpoint details

---

## Project Structure (Agent)

```
services/agent/
├── graph.py          # StateGraph definition, nodes, edges, routers
├── state.py          # AgentState TypedDict
├── trace.py          # SQLite trace store (runs + nodes tables)
├── tools/
│   ├── incident.py   # Typed, bounded incident lookup tool
│   └── inventory.py  # Typed, bounded inventory lookup tool
├── traces/           # SQLite database (runtime, gitignored)
tests/pipelines/
├── test_agent_graph.py      # 108 tests (graph structure + tools)
├── test_offline_replay.py   # 33 tests (saved-trace assertions)
scripts/
├── capture_live_agent_traces.py   # Capture real traces
├── evaluate_agent_graph.py         # Scorecard evaluation
docs/agent/
├── README.md          # This file
├── architecture.md    # Detailed architecture docs
├── EVALUATION_CHECKLIST.md  # Part1+Part2 evaluation checklist
└── validation.txt     # Latest test output
data/eval/
└── live-traces/       # Saved traces (rag.json, incident.json, both.json)
```