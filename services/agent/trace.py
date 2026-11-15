"""Durable SQLite trace store for LangGraph agent runs.

Each invocation creates a run record and logs each visited node with
timing and outcome. The store is separate from LangGraph's own
``InMemorySaver`` — it preserves high-level semantic trace data for
offline evaluation, auditing, and debugging.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TRACE_DIR = Path(__file__).resolve().parent / "traces"
_TRACE_DIR.mkdir(parents=True, exist_ok=True)
_TRACE_DB = str(_TRACE_DIR / "agent_traces.sqlite")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_TRACE_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _init_db() -> None:
    """Create schema if it does not already exist."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id          TEXT PRIMARY KEY,
                question        TEXT NOT NULL,
                classification  TEXT,
                answer          TEXT,
                outcome         TEXT NOT NULL DEFAULT 'pending',
                started_at      REAL NOT NULL,
                finished_at     REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id      TEXT NOT NULL REFERENCES runs(run_id),
                node_name   TEXT NOT NULL,
                started_at  REAL NOT NULL,
                finished_at REAL,
                status      TEXT NOT NULL DEFAULT 'running',
                details     TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_nodes_run_id ON nodes(run_id)
        """)


# Ensure schema exists at import time
_init_db()


def _normalise_outcome(state: dict[str, Any]) -> str:
    """Derive a short outcome string from agent state."""
    error = state.get("error")
    if error:
        return f"error:{error}"
    answer = state.get("answer")
    if answer:
        return "answered"
    classification = state.get("classification", "unknown")
    return f"unresolved:{classification}"


def start_run(state: dict[str, Any]) -> str:
    """Persist a new run record and return its ``run_id``."""
    run_id = str(uuid.uuid4())
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO runs (run_id, question, started_at) VALUES (?, ?, ?)",
            (run_id, state.get("question", ""), time.time()),
        )
    return run_id


def save_run_node(
    run_id: str,
    node_name: str,
    *,
    status: str = "completed",
    details: dict[str, Any] | None = None,
) -> int:
    """Log a visited node with timing and optional structured details.

    Returns the node row id.
    """
    now = time.time()
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO nodes (run_id, node_name, started_at, finished_at, "
            "status, details) VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, node_name, now, now, status, json.dumps(details) if details else None),
        )
        return cur.lastrowid


def finish_run(run_id: str, state: dict[str, Any]) -> None:
    """Mark a run as finished with final answer and outcome."""
    outcome = _normalise_outcome(state)
    with _get_conn() as conn:
        conn.execute(
            "UPDATE runs SET answer = ?, outcome = ?, finished_at = ?, "
            "classification = ? WHERE run_id = ?",
            (
                state.get("answer"),
                outcome,
                time.time(),
                state.get("classification"),
                run_id,
            ),
        )


def get_run(run_id: str) -> dict[str, Any] | None:
    """Retrieve a run and its nodes as a dict."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        nodes = conn.execute(
            "SELECT * FROM nodes WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
    return {
        "run_id": row["run_id"],
        "question": row["question"],
        "classification": row["classification"],
        "answer": row["answer"],
        "outcome": row["outcome"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "nodes": [dict(n) for n in nodes],
    }


def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    """List recent runs with summary info."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT run_id, question, classification, outcome, "
            "started_at, finished_at FROM runs "
            "ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]