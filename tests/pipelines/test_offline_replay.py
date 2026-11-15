"""Offline replay eval — read saved live traces and assert known facts.

These tests do **not** compile the graph, call Qdrant, TinyDB, or the LLM.
They read previously-captured JSON traces from ``data/eval/live-traces/``
and verify structural contracts and known facts.

Usage::

    uv run --env-file backend/.env python scripts/capture_live_agent_traces.py
    .venv/bin/python -m pytest tests/pipelines/test_offline_replay.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

TRACES_DIR = Path("data/eval/live-traces")

# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture(scope="session")
def traces_dir() -> Path:
    assert TRACES_DIR.is_dir(), (
        f"No traces directory at {TRACES_DIR}. "
        "Run `uv run --env-file backend/.env python scripts/capture_live_agent_traces.py` first."
    )
    return TRACES_DIR


def _load(name: str, traces_dir: Path) -> dict:
    path = traces_dir / name
    assert path.exists(), f"Trace file {path} not found"
    return json.loads(path.read_text())


# ======================================================================
# Structural contracts (no live services needed)
# ======================================================================


class TestOfflineTraceStructural:
    """Assert that all saved traces have the expected schema."""

    CORE_KEYS = {"classification", "answer", "run_id", "error", "question"}

    def test_all_traces_have_core_keys(self, traces_dir):
        for path in sorted(traces_dir.iterdir()):
            data = json.loads(path.read_text())
            missing = self.CORE_KEYS - set(data)
            assert not missing, f"{path.name} missing core keys: {missing}"

    def test_all_traces_have_run_id(self, traces_dir):
        for path in sorted(traces_dir.iterdir()):
            data = json.loads(path.read_text())
            rid = data.get("run_id")
            assert rid and len(rid) > 10, f"{path.name}: invalid run_id {rid!r}"

    def test_all_traces_have_no_error(self, traces_dir):
        for path in sorted(traces_dir.iterdir()):
            data = json.loads(path.read_text())
            err = data.get("error")
            assert err is None, f"{path.name}: unexpected error {err!r}"

    def test_classification_not_none(self, traces_dir):
        for path in sorted(traces_dir.iterdir()):
            data = json.loads(path.read_text())
            cls = data.get("classification")
            assert cls is not None, f"{path.name}: classification must not be None"
            assert isinstance(cls, str), f"{path.name}: classification must be a string"

    def test_answer_is_string(self, traces_dir):
        for path in sorted(traces_dir.iterdir()):
            data = json.loads(path.read_text())
            ans = data.get("answer")
            assert isinstance(ans, str), f"{path.name}: answer must be str, got {type(ans).__name__}"

    def test_all_traces_have_node_order(self, traces_dir):
        """Every trace should now contain _node_order from the SQLite trace store."""
        for path in sorted(traces_dir.iterdir()):
            data = json.loads(path.read_text())
            nodes = data.get("_node_order")
            assert nodes is not None, f"{path.name}: missing _node_order key"
            assert isinstance(nodes, list), f"{path.name}: _node_order must be a list"
            assert len(nodes) >= 1, f"{path.name}: _node_order must have at least 1 entry"
            names = [n["node_name"] for n in nodes]
            assert "receive_validate" in names, (
                f"{path.name}: _node_order must include receive_validate, got {names}"
            )


# ======================================================================
# RAG-only trace
# ======================================================================


class TestOfflineRagOnly:
    """Facts about the ``rag.json`` live trace."""

    @pytest.fixture(scope="module")
    def trace(self, traces_dir):
        return _load("rag.json", traces_dir)

    def test_classification(self, trace):
        assert trace["classification"] == "rag", (
            f"Expected 'rag', got {trace['classification']!r}"
        )

    def test_chunks_present(self, trace):
        chunks = trace.get("retrieved_chunks") or []
        assert len(chunks) >= 1, "Expected at least 1 retrieved chunk"

    def test_chunks_have_payload_text(self, trace):
        chunks = trace.get("retrieved_chunks") or []
        for c in chunks:
            payload = c.get("payload", {})
            text = payload.get("text", "")
            assert text, f"Chunk has empty payload.text: {c.get('score')}"
            section = payload.get("section", "?")
            source = payload.get("source_document", "?")
            assert section, "Chunk missing section in payload"
            assert source, "Chunk missing source_document in payload"

    def test_no_incident_result_key(self, trace):
        assert "incident_result" not in trace, (
            "RAG-only trace should not have incident_result key"
        )

    def test_no_inventory_result_key(self, trace):
        assert "inventory_result" not in trace, (
            "RAG-only trace should not have inventory_result key"
        )

    def test_answer_contains_citation(self, trace):
        answer = trace.get("answer") or ""
        # Real generated answers include a [source | Section] citation
        assert "[" in answer and "]" in answer, (
            f"Answer should contain a citation marker, got: {answer[:200]}"
        )

    def test_answer_mentions_return_window(self, trace):
        answer = trace.get("answer") or ""
        assert "30 days from delivery" in answer, (
            f"Answer should mention the 30-day return window, got: {answer[:300]}"
        )

    def test_answer_states_may_be_configured_differently(self, trace):
        answer = trace.get("answer") or ""
        assert "contract" in answer.lower(), (
            f"Answer should note the window may vary by contract, got: {answer[:300]}"
        )

    def test_node_order_retrieve_precedes_generate(self, trace):
        nodes = trace.get("_node_order", [])
        names = [n["node_name"] for n in nodes]
        assert "retrieve_context" in names, (
            f"_node_order missing retrieve_context: {names}"
        )
        assert "generate_answer" in names, (
            f"_node_order missing generate_answer: {names}"
        )
        assert names.index("retrieve_context") < names.index("generate_answer"), (
            f"retrieve_context must precede generate_answer: {names}"
        )

    def test_no_incident_or_inventory_nodes(self, trace):
        """RAG-only path should NOT visit incident or inventory tool nodes."""
        nodes = trace.get("_node_order", [])
        names = [n["node_name"] for n in nodes]
        for skipped in ("lookup_incident", "lookup_inventory"):
            assert skipped not in names, (
                f"RAG-only trace should not have visited {skipped}: {names}"
            )


# ======================================================================
# Incident-only trace
# ======================================================================


class TestOfflineIncidentOnly:
    """Facts about the ``incident.json`` live trace."""

    @pytest.fixture(scope="module")
    def trace(self, traces_dir):
        return _load("incident.json", traces_dir)

    def test_classification(self, trace):
        assert trace["classification"] in ("ticket", "both"), (
            f"Expected 'ticket' or 'both', got {trace['classification']!r}"
        )

    def test_no_retrieved_chunks_key(self, trace):
        assert "retrieved_chunks" not in trace, (
            f"Incident-only trace should not have retrieved_chunks key, got {trace.get('retrieved_chunks')}"
        )

    def test_incident_result_present(self, trace):
        inc = trace.get("incident_result")
        assert inc is not None, "Expected incident_result to be present"

    def test_incident_result_fields(self, trace):
        inc = trace.get("incident_result") or {}
        for key in ("id", "title", "description", "category",
                    "status", "origin", "branch", "created_at", "updated_at"):
            assert key in inc, f"incident_result missing key {key!r}"
            assert isinstance(inc.get(key), str), f"incident_result.{key} must be a string"

    def test_incident_id_matches_known_value(self, trace):
        inc = trace.get("incident_result") or {}
        iid = inc.get("id", "")
        assert iid == "95b5f484-b729-4e40-a149-c023386db302", (
            f"Expected known incident ID, got {iid!r}"
        )

    def test_incident_status_is_open(self, trace):
        inc = trace.get("incident_result") or {}
        assert inc.get("status") == "open", (
            f"Expected status='open', got {inc.get('status')!r}"
        )

    def test_incident_category(self, trace):
        inc = trace.get("incident_result") or {}
        assert inc.get("category") == "lost_parcel", (
            f"Expected category='lost_parcel', got {inc.get('category')!r}"
        )

    def test_answer_contains_incident_title(self, trace):
        answer = trace.get("answer") or ""
        assert "Incident regarding lost parcel" in answer, (
            f"Answer should contain the incident title, got: {answer[:200]}"
        )

    def test_node_order_tool_only_skips_rag(self, trace):
        """Ticket-only path: incident lookup but NO retrieve/generate."""
        nodes = trace.get("_node_order", [])
        names = [n["node_name"] for n in nodes]
        assert "lookup_incident" in names, (
            f"_node_order missing lookup_incident: {names}"
        )
        assert "retrieve_context" not in names, (
            f"Ticket-only trace should not visit retrieve_context: {names}"
        )
        assert "generate_answer" not in names, (
            f"Ticket-only trace should not visit generate_answer: {names}"
        )


# ======================================================================
# Both trace (RAG + incident)
# ======================================================================


class TestOfflineBoth:
    """Facts about the ``both.json`` live trace."""

    @pytest.fixture(scope="module")
    def trace(self, traces_dir):
        return _load("both.json", traces_dir)

    def test_classification(self, trace):
        assert trace["classification"] == "both", (
            f"Expected 'both', got {trace['classification']!r}"
        )

    def test_both_chunks_and_incident_present(self, trace):
        chunks = trace.get("retrieved_chunks") or []
        inc = trace.get("incident_result")
        assert len(chunks) >= 1, "Expected RAG chunks for 'both' trace"
        assert inc is not None, "Expected incident_result for 'both' trace"

    def test_incident_id_known(self, trace):
        inc = trace.get("incident_result") or {}
        assert inc.get("id") == "95b5f484-b729-4e40-a149-c023386db302"

    def test_answer_mentions_policy(self, trace):
        answer = trace.get("answer") or ""
        # The answer should reference indexed documents or return policy
        assert any(term in answer.lower() for term in
                   ("return", "policy", "document", "indexed", "incident")), (
            f"Answer does not seem to reference policy, got: {answer[:200]}"
        )

    def test_chunk_text_preserved(self, trace):
        chunks = trace.get("retrieved_chunks") or []
        # The top chunk is from returns-policy / Returns Policy
        top_payload = chunks[0].get("payload", {})
        text = top_payload.get("text", "")
        assert "return window" in text.lower(), (
            f"Top chunk text should mention return window, got: {text[:200]}"
        )

    def test_node_order_both_path(self, trace):
        """'both' path: incident lookup THEN retrieve THEN generate."""
        nodes = trace.get("_node_order", [])
        names = [n["node_name"] for n in nodes]
        for expected in ("lookup_incident", "retrieve_context", "generate_answer"):
            assert expected in names, (
                f"_node_order missing {expected}: {names}"
            )
        assert names.index("retrieve_context") < names.index("generate_answer"), (
            f"retrieve_context must precede generate_answer: {names}"
        )

    def test_answer_states_30_day_policy_fact(self, trace):
        answer = trace.get("answer") or ""
        assert "30-day return window" in answer or "30 days from delivery" in answer, (
            f"Answer should state the actual 30-day policy, got: {answer[:300]}"
        )


# ======================================================================
# Tool-only contract (no graph compilation required)
# ======================================================================


class TestOfflineToolContract:
    """Verify that the saved tool result matches the typed contract."""

    def test_incident_lookup_response_has_all_fields(self, traces_dir):
        """Check that incident_result fields match ``IncidentLookupResponse``."""
        for name in ("incident.json", "both.json"):
            data = json.loads((traces_dir / name).read_text())
            inc = data.get("incident_result")
            if inc is None:
                continue
            for key in ("id", "title", "description", "category",
                        "status", "origin", "branch", "created_at", "updated_at"):
                assert key in inc, f"{name}: incident_result missing {key!r}"
                val = inc[key]
                assert isinstance(val, str), (
                    f"{name}: incident_result.{key} should be str, got {type(val).__name__}"
                )