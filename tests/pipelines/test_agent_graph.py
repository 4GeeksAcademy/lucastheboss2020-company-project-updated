"""Comprehensive tests for the LangGraph agent graph.

Test categories
---------------
1. Graph structure — nodes, edges, compilation
2. Node isolation — each node function tested in isolation
3. Classification logic — all keyword categories
4. Conditional routing — edge behaviour per classification path
5. Trace integration — run_id creation, node logging, finish
6. Write-intent rejection — detection, routing, and output
7. Bounded incident tool — timeout behaviour
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from services.agent.graph import (
    _classify_router,
    _after_incident_router,
    _retrieve_router,
    assemble_final,
    build_agent,
    classify_question,
    fallback,
    generate_answer,
    lookup_incident,
    lookup_inventory,
    receive_validate,
    reject_write_intent,
    retrieve_context,
    route_classify,
)
from services.agent.state import AgentState

# =========================================================================
# 1. Graph structure
# =========================================================================


class TestGraphStructure:
    """Verify the graph compiles and has the expected shape."""

    def test_build_agent_returns_state_graph(self):
        """``build_agent()`` should return a ``StateGraph``."""
        from langgraph.graph import StateGraph

        sg = build_agent()
        assert isinstance(sg, StateGraph)

    def test_all_nodes_registered(self):
        """Every expected node should be registered."""
        sg = build_agent()
        expected_nodes = {
            "receive_validate",
            "route_classify",
            "reject_write_intent",
            "lookup_incident",
            "lookup_inventory",
            "retrieve_context",
            "generate_answer",
            "fallback",
            "assemble_final",
        }
        registered = set(sg.nodes.keys())
        for name in expected_nodes:
            assert name in registered, f"Node {name!r} not registered"

    def test_entry_and_finish_points(self):
        """Entry should be ``receive_validate``, finish ``assemble_final``."""
        sg = build_agent()
        # Entry point is the node that __start__ connects to
        edges = sg.edges
        entry_nodes = [t for (s, t) in edges if s == "__start__"]
        finish_nodes = [s for (s, t) in edges if t == "__end__"]
        assert "receive_validate" in entry_nodes, (
            f"Expected receive_validate as entry, got {entry_nodes}"
        )
        assert "assemble_final" in finish_nodes, (
            f"Expected assemble_final as finish, got {finish_nodes}"
        )

    def test_unconditional_edges(self):
        """Verify unconditional edges exist."""
        sg = build_agent()
        # StateGraph stores edges as tuples: (source, target)
        edges = {e for e in sg.edges}
        expected = {
            ("receive_validate", "route_classify"),
            ("reject_write_intent", "assemble_final"),
            ("lookup_inventory", "assemble_final"),
            ("generate_answer", "assemble_final"),
            ("fallback", "assemble_final"),
        }
        assert expected.issubset(edges), f"Missing unconditional edges: {expected - edges}"

    def test_compile_with_inmemory_saver(self):
        """Should compile with ``InMemorySaver`` checkpointer."""
        from langgraph.checkpoint.memory import InMemorySaver

        sg = build_agent()
        graph = sg.compile(checkpointer=InMemorySaver())
        assert hasattr(graph, "invoke")
        assert hasattr(graph, "stream")

    def test_compile_without_checkpointer(self):
        """Should also compile without a checkpointer."""
        sg = build_agent()
        graph = sg.compile()
        assert hasattr(graph, "invoke")

    def test_invoke_returns_dict(self):
        """A basic invoke should return a dict with answer."""
        from langgraph.checkpoint.memory import InMemorySaver

        sg = build_agent()
        graph = sg.compile(checkpointer=InMemorySaver())
        result = graph.invoke(
            {"question": "Hello world"},
            config={"configurable": {"thread_id": "test-struct-1"}},
        )
        assert isinstance(result, dict)
        assert "answer" in result
        assert result.get("classification") == "unknown"


# =========================================================================
# 2. Classification logic
# =========================================================================


class TestClassification:
    """Test the ``classify_question`` helper."""

    @pytest.mark.parametrize(
        "question, expected",
        [
            # RAG keywords
            ("What is the return policy?", "rag"),
            ("What is the SLA for deliveries?", "rag"),
            ("Tell me about storage pricing", "rag"),
            ("What are the carrier coverage terms?", "rag"),
            ("I need the terms and conditions", "rag"),
            # Ticket keywords
            ("Check incident TRF-abc12345", "ticket"),
            ("I have a complaint about a lost parcel", "ticket"),
            ("Track package TRF-xyz", "ticket"),
            ("My delivery is delayed", "ticket"),
            ("There is damage to my parcel", "ticket"),
            # Inventory keywords
            ("Show me current stock levels", "inventory"),
            ("What products do we have in warehouse?", "inventory"),
            ("Check SKU availability", "inventory"),
            ("Check stock quantity for fashion-co", "inventory"),
            # Both incident AND RAG
            ("What is the SLA for incident TRF-abc12345?", "both"),
            ("Check the return policy for my damaged parcel", "both"),
            # Unknown / garbage
            ("Hello world", "unknown"),
            ("", "unknown"),
            ("What is the weather?", "unknown"),
            # Write-intent — create / update / delete ticket or incident
            ("Create a new incident for a lost package", "write_intent"),
            ("Update incident TRF-abc12345 with new details", "write_intent"),
            ("Delete ticket TRF-xyz", "write_intent"),
            ("Close incident TRF-abc12345", "write_intent"),
            ("Cancel my ticket", "write_intent"),
            ("Modify the inventory for SKU-001", "write_intent"),
            ("Add a new product to inventory", "write_intent"),
            ("Remove item from stock", "write_intent"),
            ("Change the status of incident TRF-abc", "write_intent"),
            # Pure read with write-looking words — these are false positives
            # in the heuristic keyword matcher (write keyword + incident keyword),
            # but the trade-off is acceptable since write-intent detection is
            # the priority.
            ("What is the create date on this ticket?", "write_intent"),
            # "incidents" (plural) doesn't match "incident" keyword, so unknown
            ("Show me newly created incidents", "unknown"),
        ],
    )
    def test_classify(self, question, expected):
        assert classify_question(question) == expected


# =========================================================================
# 3. Node isolation
# =========================================================================


class TestReceiveValidate:
    """``receive_validate`` node in isolation."""

    def test_sets_run_id_and_error_none(self):
        state: AgentState = {"question": "What is the policy?"}
        result = receive_validate(state)
        assert result.get("run_id") is not None
        assert result.get("error") is None

    def test_raises_on_blank(self):
        state: AgentState = {"question": ""}
        result = receive_validate(state)
        assert result.get("error") == "BLANK_QUESTION"

    def test_raises_on_whitespace(self):
        state: AgentState = {"question": "   "}
        result = receive_validate(state)
        assert result.get("error") == "BLANK_QUESTION"


class TestRouteClassify:
    """``route_classify`` node in isolation."""

    def test_sets_classification(self):
        state: AgentState = {"question": "What is the SLA?"}
        result = route_classify(state)
        assert result.get("classification") == "rag"

    def test_skips_on_error(self):
        state: AgentState = {"question": "test", "error": "BLANK_QUESTION"}
        result = route_classify(state)
        assert result.get("classification") is None

    def test_inventory(self):
        state: AgentState = {"question": "Show stock levels"}
        result = route_classify(state)
        assert result.get("classification") == "inventory"

    def test_ticket(self):
        state: AgentState = {"question": "Check incident TRF-abc12345"}
        result = route_classify(state)
        assert result.get("classification") == "ticket"

    def test_write_intent(self):
        """Write-intent questions should produce 'write_intent' classification."""
        state: AgentState = {"question": "Create a new incident for a lost package"}
        result = route_classify(state)
        assert result.get("classification") == "write_intent"


class TestRejectWriteIntent:
    """``reject_write_intent`` node in isolation."""

    def test_sets_write_intent_answer(self):
        state: AgentState = {
            "question": "Create a new incident",
            "classification": "write_intent",
        }
        result = reject_write_intent(state)
        assert result.get("classification") == "write_intent"
        answer = result.get("answer", "")
        assert "read-only" in answer.lower()
        assert "change" in answer.lower() or "create" in answer.lower()

    def test_preserves_error(self):
        """If an error is already set, answer should still be set."""
        state: AgentState = {
            "question": "Delete ticket TRF-abc",
            "classification": "write_intent",
            "error": "SOME_ERROR",
        }
        result = reject_write_intent(state)
        assert result.get("answer") is not None
        assert "read-only" in result["answer"].lower()

    def test_mentions_trackflow_team(self):
        """Rejection should direct users to contact TrackFlow support."""
        state: AgentState = {
            "question": "Update incident TRF-abc",
            "classification": "write_intent",
        }
        result = reject_write_intent(state)
        answer = result.get("answer", "")
        assert "TrackFlow" in answer or "team" in answer or "support" in answer


class TestLookupIncident:
    """``lookup_incident`` node in isolation."""

    def test_skips_on_error(self):
        state: AgentState = {"question": "test", "error": "SOME_ERROR"}
        result = lookup_incident(state)
        assert result.get("error") == "SOME_ERROR"  # preserved

    def test_no_incident_id(self):
        state: AgentState = {"question": "Tell me about incidents"}
        result = lookup_incident(state)
        assert result.get("error") == "NO_INCIDENT_ID"
        assert result.get("incident_result") is None

    def test_lookup_unknown_id(self):
        state: AgentState = {"question": "Check incident UNKNOWN-12345678"}
        result = lookup_incident(state)
        # In test env, get_incident will return None for unknown IDs
        assert result.get("error") in ("INCIDENT_NOT_FOUND", None)


class TestLookupInventory:
    """``lookup_inventory`` node in isolation."""

    def test_skips_on_error(self):
        state: AgentState = {"question": "test", "error": "SOME_ERROR"}
        result = lookup_inventory(state)
        assert result.get("error") == "SOME_ERROR"

    def test_handles_db_not_configured(self):
        """Without DATABASE_URL, should set an error gracefully."""
        state: AgentState = {"question": "Show stock levels"}
        result = lookup_inventory(state)
        # Either succeeds (if DB is configured) or sets inventory error
        if result.get("error") == "INVENTORY_LOOKUP_FAILED":
            assert result.get("inventory_result") == []
        else:
            # DB is configured — should have results
            assert result.get("inventory_result") is not None


class TestRetrieveContext:
    """``retrieve_context`` node in isolation."""

    def test_skips_on_error(self):
        state: AgentState = {"question": "test", "error": "SOME_ERROR"}
        result = retrieve_context(state)
        assert result.get("error") == "SOME_ERROR"

    def test_sets_chunks_even_when_empty(self):
        """Retrieval should produce a list (possibly empty)."""
        state: AgentState = {"question": "Something unknown"}
        result = retrieve_context(state)
        assert isinstance(result.get("retrieved_chunks"), list)


class TestGenerateAnswer:
    """``generate_answer`` node in isolation."""

    def test_skips_on_error(self):
        state: AgentState = {"question": "test", "error": "SOME_ERROR"}
        result = generate_answer(state)
        assert result.get("error") == "SOME_ERROR"

    def test_empty_chunks_returns_empty_string(self):
        state: AgentState = {
            "question": "test",
            "retrieved_chunks": [],
        }
        result = generate_answer(state)
        assert result.get("generated_answer") == ""

    def test_no_chunks_key(self):
        state: AgentState = {"question": "test"}
        result = generate_answer(state)
        assert result.get("generated_answer") == ""


class TestFallback:
    """``fallback`` node in isolation."""

    def test_sets_answer_for_no_error(self):
        state: AgentState = {"question": "Hello world"}
        result = fallback(state)
        assert "not sure how to help" in result.get("answer", "")

    def test_sets_answer_for_blank_error(self):
        state: AgentState = {"question": "", "error": "BLANK_QUESTION"}
        result = fallback(state)
        assert "not sure how to help" in result.get("answer", "")

    def test_preserves_other_errors(self):
        state: AgentState = {"question": "test", "error": "INCIDENT_LOOKUP_FAILED"}
        result = fallback(state)
        # fallback only sets answer if error is None or BLANK_QUESTION
        assert result.get("answer") is None or "not sure" in result["answer"]


class TestAssembleFinal:
    """``assemble_final`` node in isolation."""

    def test_error_message_mapping(self):
        for error_code, expected_prefix in [
            ("BLANK_QUESTION", "I need a question"),
            ("NO_INCIDENT_ID", "Please provide an incident"),
            ("INCIDENT_NOT_FOUND", "No incident found"),
            ("INCIDENT_LOOKUP_FAILED", "temporarily unavailable"),
            ("INVENTORY_LOOKUP_FAILED", "temporarily unavailable"),
            ("GENERATION_FAILED", "unable to generate"),
        ]:
            state: AgentState = {"question": "test", "error": error_code}
            result = assemble_final(state)
            assert expected_prefix in result.get("answer", ""), (
                f"Error {error_code!r}: expected {expected_prefix!r} in answer, "
                f"got {result.get('answer')!r}"
            )

    def test_generated_answer_included(self):
        state: AgentState = {
            "question": "test",
            "classification": "rag",
            "generated_answer": "This is the return policy...",
        }
        result = assemble_final(state)
        assert "This is the return policy" in result.get("answer", "")

    def test_incident_included(self):
        state: AgentState = {
            "question": "test",
            "classification": "ticket",
            "incident_result": {
                "id": "TRF-12345",
                "title": "Lost package",
                "status": "open",
                "category": "loss",
                "branch": "los_angeles",
                "description": "Package lost in transit",
            },
        }
        result = assemble_final(state)
        answer = result.get("answer", "")
        assert "TRF-12345" in answer
        assert "Lost package" in answer
        assert "open" in answer

    def test_inventory_included(self):
        state: AgentState = {
            "question": "test",
            "classification": "inventory",
            "inventory_result": [
                {"name": "T-Shirt", "sku": "TS-001", "warehouse": "LA",
                 "current_stock": 42},
                {"name": "Jeans", "sku": "JN-001", "warehouse": "LA",
                 "current_stock": 15},
            ],
        }
        result = assemble_final(state)
        answer = result.get("answer", "")
        assert "T-Shirt" in answer
        assert "42 units" in answer
        assert "Jeans" in answer

    def test_unknown_classification_message(self):
        state: AgentState = {
            "question": "Hello world",
            "classification": "unknown",
        }
        result = assemble_final(state)
        assert "not sure how to help" in result.get("answer", "")

    def test_empty_parts_with_known_classification(self):
        state: AgentState = {
            "question": "test",
            "classification": "rag",
            "retrieved_chunks": [],
            "generated_answer": "",
        }
        result = assemble_final(state)
        assert "No information was found" in result.get("answer", "")

    def test_preserves_fallback_answer_for_unknown(self):
        """When fallback already set an answer, assemble_final should keep it."""
        state: AgentState = {
            "question": "Hello world",
            "classification": "unknown",
            "answer": "I'm not sure how to help with that.",
        }
        result = assemble_final(state)
        assert result.get("answer") == "I'm not sure how to help with that."

    def test_preserves_write_intent_answer(self):
        """When reject_write_intent already set an answer, assemble_final should keep it."""
        state: AgentState = {
            "question": "Create a new incident",
            "classification": "write_intent",
            "answer": "I'm sorry, but I can only provide read-only answers...",
        }
        result = assemble_final(state)
        assert "read-only" in result.get("answer", "").lower()


# =========================================================================
# 4. Conditional routing
# =========================================================================


class TestConditionalRouting:
    """Test the routing functions used in conditional edges."""

    @pytest.mark.parametrize(
        "state, expected_target",
        [
            ({"classification": "rag"}, "retrieve_context"),
            ({"classification": "ticket"}, "lookup_incident"),
            ({"classification": "both"}, "lookup_incident"),
            ({"classification": "inventory"}, "lookup_inventory"),
            ({"classification": "write_intent"}, "reject_write_intent"),
            ({"classification": "unknown"}, "fallback"),
            ({}, "fallback"),
            ({"classification": None}, "fallback"),
        ],
    )
    def test_classify_router(self, state, expected_target):
        assert _classify_router(state) == expected_target

    @pytest.mark.parametrize(
        "state, expected_target",
        [
            ({"classification": "both"}, "retrieve_context"),
            ({"classification": "ticket"}, "assemble_final"),
            ({"classification": "rag"}, "assemble_final"),
            ({"classification": "inventory"}, "assemble_final"),
            ({"classification": "unknown"}, "assemble_final"),
            ({}, "assemble_final"),
        ],
    )
    def test_after_incident_router(self, state, expected_target):
        assert _after_incident_router(state) == expected_target

    @pytest.mark.parametrize(
        "state, expected_target",
        [
            ({"retrieved_chunks": [{"score": 0.9}]}, "generate_answer"),
            ({"retrieved_chunks": []}, "fallback"),
            ({}, "fallback"),
            ({"retrieved_chunks": None}, "fallback"),
        ],
    )
    def test_retrieve_router(self, state, expected_target):
        assert _retrieve_router(state) == expected_target


class TestConditionalEdgeExecution:
    """Test that the full graph routes through correct paths."""

    @pytest.fixture(autouse=True)
    def _compiled_graph(self):
        from langgraph.checkpoint.memory import InMemorySaver

        sg = build_agent()
        self.graph = sg.compile(checkpointer=InMemorySaver())

    def _invoke(self, question: str, thread_id: str = "test") -> AgentState:
        return self.graph.invoke(
            {"question": question},
            config={"configurable": {"thread_id": thread_id}},
        )

    def test_rag_path(self):
        """RAG question → route_classify → retrieve_context → generate_answer → assemble_final"""
        result = self._invoke("What is the return policy?", "test-rag")
        assert result.get("classification") == "rag"
        assert result.get("answer") is not None

    def test_ticket_path(self):
        """Ticket question → route_classify → lookup_incident → assemble_final"""
        result = self._invoke("Check incident TRF-abc12345", "test-ticket")
        assert result.get("classification") == "ticket"
        # Incident won't be found in test env, so error is set
        assert result.get("error") in (None, "INCIDENT_NOT_FOUND", "NO_INCIDENT_ID")

    def test_inventory_path(self):
        """Inventory question → route_classify → lookup_inventory → assemble_final"""
        result = self._invoke("Show me current stock levels", "test-inventory")
        assert result.get("classification") == "inventory"
        # DB might not be configured, so either answer or error
        assert result.get("answer") is not None

    def test_unknown_path(self):
        """Unknown question → route_classify → fallback → assemble_final"""
        result = self._invoke("Hello world", "test-unknown")
        assert result.get("classification") == "unknown"
        assert "not sure how to help" in result.get("answer", "")

    def test_blank_path(self):
        """Blank question → receive_validate (sets error) → route_classify (skips) → ... → assemble_final"""
        result = self._invoke("", "test-blank")
        assert result.get("error") == "BLANK_QUESTION"
        assert result.get("answer") is not None

    def test_both_path(self):
        """Both (incident+RAG) question → classify(both) → lookup_incident → retrieve_context → generate_answer → assemble_final"""
        result = self._invoke("What is the SLA for incident TRF-abc12345?", "test-both")
        assert result.get("classification") == "both"
        assert result.get("answer") is not None

    def test_write_intent_path(self):
        """Write-intent question → route_classify → reject_write_intent → assemble_final"""
        result = self._invoke("Create a new incident for a lost package", "test-write-intent")
        assert result.get("classification") == "write_intent"
        answer = result.get("answer", "")
        assert "read-only" in answer.lower(), (
            f"Write-intent answer should mention read-only, got: {answer}"
        )

    def test_write_intent_delete_ticket(self):
        """Delete ticket should also route through reject_write_intent."""
        result = self._invoke("Delete ticket TRF-abc123", "test-write-intent-2")
        assert result.get("classification") == "write_intent"
        assert "read-only" in result.get("answer", "").lower()

    def test_write_intent_change_incident(self):
        """Change/update incident should route through reject_write_intent."""
        result = self._invoke("Change the status of incident TRF-abc to resolved", "test-write-intent-3")
        assert result.get("classification") == "write_intent"
        assert "read-only" in result.get("answer", "").lower()

    def test_write_intent_inventory_modify(self):
        """Modify inventory should route through reject_write_intent."""
        result = self._invoke("Modify the inventory for SKU-001", "test-write-intent-4")
        assert result.get("classification") == "write_intent"
        assert "read-only" in result.get("answer", "").lower()


# =========================================================================
# 5. Trace integration
# =========================================================================


class TestTraceIntegration:
    """Verify the graph writes to the SQLite trace store."""

    def test_run_id_is_persistent(self):
        from langgraph.checkpoint.memory import InMemorySaver
        from services.agent.trace import get_run

        sg = build_agent()
        graph = sg.compile(checkpointer=InMemorySaver())

        result = graph.invoke(
            {"question": "Hello world"},
            config={"configurable": {"thread_id": "test-trace-1"}},
        )
        run_id = result.get("run_id")
        assert run_id is not None, "run_id should be set"

        run_data = get_run(run_id)
        assert run_data is not None, f"Run {run_id} should exist in trace store"
        assert run_data["question"] == "Hello world"
        assert run_data["classification"] == "unknown"
        assert run_data["outcome"] == "answered"
        assert len(run_data["nodes"]) >= 1, "At least one node should be logged"

    def test_blank_question_stores_trace(self):
        """Even blank questions must store a trace (start_run before validation)."""
        from langgraph.checkpoint.memory import InMemorySaver
        from services.agent.trace import get_run

        sg = build_agent()
        graph = sg.compile(checkpointer=InMemorySaver())

        result = graph.invoke(
            {"question": ""},
            config={"configurable": {"thread_id": "test-trace-blank"}},
        )
        run_id = result.get("run_id")
        assert run_id is not None, "run_id should be set even for blank questions"

        run_data = get_run(run_id)
        assert run_data is not None, f"Run {run_id} should exist in trace store"
        assert run_data["question"] == ""
        assert run_data["classification"] is None
        # The trace record should exist even though validation fails
        assert run_data["outcome"] == "error:BLANK_QUESTION", (
            f"Expected error:BLANK_QUESTION, got {run_data['outcome']!r}"
        )

    def test_runs_listed(self):
        from services.agent.trace import list_runs

        runs = list_runs()
        assert isinstance(runs, list)
        if runs:
            assert "run_id" in runs[0]
            assert "question" in runs[0]
            assert "outcome" in runs[0]

    def test_write_intent_trace_persisted(self):
        """Write-intent rejections must also create trace records."""
        from langgraph.checkpoint.memory import InMemorySaver
        from services.agent.trace import get_run

        sg = build_agent()
        graph = sg.compile(checkpointer=InMemorySaver())

        result = graph.invoke(
            {"question": "Create a new incident"},
            config={"configurable": {"thread_id": "test-trace-write"}},
        )
        run_id = result.get("run_id")
        assert run_id is not None

        run_data = get_run(run_id)
        assert run_data is not None
        assert run_data["classification"] == "write_intent"
        assert run_data["outcome"] == "answered"


# =========================================================================
# 6. Bounded incident tool
# =========================================================================


class TestBoundedIncidentTool:
    """Verify the incident tool enforces its timeout and validates input."""

    def test_import_tool(self):
        from services.agent.tools.incident import (
            IncidentLookupInput,
            IncidentLookupResponse,
            IncidentToolError,
            lookup_incident_by_id,
        )
        assert callable(lookup_incident_by_id)
        # Verify typed contracts exist
        assert "incident_id" in IncidentLookupInput.__annotations__
        assert "id" in IncidentLookupResponse.__annotations__
        assert "title" in IncidentLookupResponse.__annotations__
        assert "description" in IncidentLookupResponse.__annotations__
        assert "category" in IncidentLookupResponse.__annotations__
        assert "status" in IncidentLookupResponse.__annotations__
        assert "origin" in IncidentLookupResponse.__annotations__
        assert "branch" in IncidentLookupResponse.__annotations__

    def test_tool_returns_none_for_unknown(self):
        from services.agent.tools.incident import lookup_incident_by_id
        result = lookup_incident_by_id("UNKNOWN-99999999")
        assert result is None

    def test_tool_returns_typed_response(self):
        """A known incident should return an IncidentLookupResponse with fields."""
        from services.agent.tools.incident import (
            IncidentLookupResponse,
            lookup_incident_by_id,
        )
        result = lookup_incident_by_id("TRF-test-typed-contract")
        if result is not None:
            assert isinstance(result, dict)
            for key in ("id", "title", "description", "category",
                        "status", "origin", "branch", "created_at", "updated_at"):
                assert key in result, f"Missing key {key!r} in response"

    def test_timeout_enforced_with_sleeping_stub(self, monkeypatch):
        """timeout=0.03s, stub sleeps 0.2s -> must return in <0.15s.

        Verifies that ``lookup_incident_by_id`` does **not** wait for a
        hung worker to complete — the ``Future.cancel()`` call after
        ``TimeoutError`` must return control immediately.
        """
        import time

        import services.agent.tools.incident as incident_mod

        # Patch the already-imported get_incident to sleep for 0.2 s.
        def _slow_get_incident(_id: str) -> dict | None:
            time.sleep(0.2)
            return None

        monkeypatch.setattr(incident_mod, "get_incident", _slow_get_incident)

        t0 = time.monotonic()
        with pytest.raises(incident_mod.IncidentToolError):
            incident_mod.lookup_incident_by_id("TRF-hang-stub", timeout=0.03)
        elapsed = time.monotonic() - t0
        assert elapsed < 0.15, (
            f"Timeout took {elapsed:.3f}s, expected < 0.15 s — "
            f"the call waited for the sleeping stub instead of bounding."
        )


class TestBoundedInventoryTool:
    """Verify the inventory tool enforces its timeout and validates contract."""

    def test_import_tool(self):
        from services.agent.tools.inventory import (
            InventoryLookupInput,
            InventoryLookupResponse,
            InventoryToolError,
            lookup_inventory,
        )
        assert callable(lookup_inventory)
        assert "id" in InventoryLookupResponse.__annotations__
        assert "name" in InventoryLookupResponse.__annotations__
        assert "sku" in InventoryLookupResponse.__annotations__
        assert "client_name" in InventoryLookupResponse.__annotations__
        assert "category" in InventoryLookupResponse.__annotations__
        assert "warehouse" in InventoryLookupResponse.__annotations__
        assert "current_stock" in InventoryLookupResponse.__annotations__

    def test_tool_returns_list_or_detects_missing_db(self):
        """With a real DB returns a list; without DATABASE_URL raises gracefully."""
        from services.agent.tools.inventory import (
            InventoryToolError,
            lookup_inventory,
        )
        try:
            result = lookup_inventory(timeout=5.0)
            assert isinstance(result, list)
        except InventoryToolError:
            pass  # No DATABASE_URL — still bounded, not hanging

    def test_timeout_enforced_with_sleeping_stub(self, monkeypatch):
        """timeout=0.03s, stub sleeps 0.2s -> must return in <0.15s."""
        import time

        import services.agent.tools.inventory as inventory_mod

        def _slow_lookup() -> list[dict]:
            time.sleep(0.2)
            return []

        monkeypatch.setattr(inventory_mod, "_do_lookup", _slow_lookup)

        t0 = time.monotonic()
        with pytest.raises(inventory_mod.InventoryToolError):
            inventory_mod.lookup_inventory(timeout=0.03)
        elapsed = time.monotonic() - t0
        assert elapsed < 0.15, (
            f"Timeout took {elapsed:.3f}s, expected < 0.15 s — "
            f"the call waited for the sleeping stub instead of bounding."
        )