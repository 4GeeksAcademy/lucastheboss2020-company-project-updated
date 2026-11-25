"""Each department has its own durable LangGraph thread and real human interrupt."""
import asyncio
from contextlib import contextmanager
from pathlib import Path
import tempfile
import time
from typing import TypedDict
from weakref import WeakKeyDictionary
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from sqlmodel import Session, select
from services.rfp_intake.models import Ticket, DepartmentSection
from services.rfp_approval.models import ApprovalTrace
from .proposal_agents import GENERATORS, ProposalModel, evaluate, policies
from .approval_rules import MAX_REVISIONS, capacity_revision_valid

_local_checkpoint_paths = WeakKeyDictionary()


@contextmanager
def checkpoint_saver(engine):
    """Use the configured database, not RAM, for graph pauses and pending writes."""
    if engine.dialect.name == "postgresql":
        from langgraph.checkpoint.postgres import PostgresSaver
        url = engine.url.set(drivername="postgresql").render_as_string(hide_password=False)
        with PostgresSaver.from_conn_string(url) as saver:
            # Multiple department workers may start together on a fresh database.
            # Serialize only schema setup, never a human's pending approval.
            # A blocking SELECT pg_advisory_lock holds a query snapshot while
            # waiting. CREATE INDEX CONCURRENTLY inside setup waits for that
            # snapshot, causing a startup deadlock. Try-lock queries finish
            # immediately and release their snapshots between attempts.
            started = time.monotonic()
            while not saver.conn.execute("SELECT pg_try_advisory_lock(904003) AS acquired").fetchone()["acquired"]:
                if time.monotonic() - started > 45:
                    raise RuntimeError("Checkpoint schema setup is busy; retry saved processing.")
                time.sleep(0.05)
            try:
                saver.setup()
            finally:
                saver.conn.execute("SELECT pg_advisory_unlock(904003)")
            yield saver
    elif engine.dialect.name == "sqlite":
        from langgraph.checkpoint.sqlite import SqliteSaver
        database = engine.url.database
        if database and database != ":memory:":
            path = str(Path(database).resolve()) + ".rfp-checkpoints.sqlite"
        else:
            if engine not in _local_checkpoint_paths:
                handle = tempfile.NamedTemporaryFile(prefix="trackflow-checkpoints-", suffix=".sqlite", delete=False)
                handle.close()
                _local_checkpoint_paths[engine] = handle.name
            path = _local_checkpoint_paths[engine]
        with SqliteSaver.from_conn_string(path) as saver:
            yield saver
    else:
        raise RuntimeError("Approval checkpoints require PostgreSQL or SQLite.")


class ApprovalState(TypedDict, total=False):
    ticket_id: str
    department_id: str
    response: dict
    version: int


def department_approval_graph(store, ticket_id, department, token, saver, model=None):
    def log(agent, input, output):
        with Session(store.engine) as db:
            store.trace(db, ticket_id, department, agent, input, output)
            db.commit()

    def arbitration(state):
        found = store.arbitrate(ticket_id)
        log("department_arbitration", {"department": department}, {"conflicts": found})
        return {}

    def human_approval(state):
        b = store.branch(ticket_id, department)
        log("human_approval_interrupt", {"draft": b.draft, "evaluation": b.evaluation, "version": b.version}, {"waiting_for": department})
        response = interrupt({"ticket_id": ticket_id, "department_id": department, "version": b.version,
                              "draft": b.draft, "evaluation": b.evaluation})
        if response.get("decision") not in {"approve", "reject", "request_changes"} or response.get("version") != b.version:
            raise ValueError("Invalid human resume response.")
        # HTTP accepts decisions only from authenticated assigned owners/arbiter.
        # Resume payload must also match the persisted outbox, never arbitrary graph input.
        if not b.response or response != b.response:
            raise ValueError("Human response does not match the persisted decision.")
        log("human_approval_resume", {"response": response}, {"validated": True})
        return {"response": response, "version": b.version}

    def record(state):
        store.apply(ticket_id, department, token, state["response"])
        return {}

    def revise(state):
        b = store.branch(ticket_id, department)
        if b.version > state["version"]:
            return {"version": b.version}
        if b.revision_count >= MAX_REVISIONS:
            raise ValueError("Human revision limit reached.")
        with Session(store.engine) as db:
            t = db.get(Ticket, ticket_id)
            section = db.exec(select(DepartmentSection).where(DepartmentSection.ticket_id == ticket_id,
                              DepartmentSection.department_id == department)).one()
            context = {"section_id": section.section_id, "department_id": department, "metadata": t.handoff["metadata"],
                       "key_aspects": section.key_aspects, "open_questions": section.open_questions, "policy_sources": policies()}
        # Preserve signed human commercial facts as source DATA. They never
        # override currency, capacity, confidentiality or other policy checks.
        context["metadata"] = dict(context["metadata"], human_review_feedback={
            "actor": state["response"]["actor"], "feedback": state["response"]["feedback"]})
        if department == "lastmile":
            warehouse = store.branch(ticket_id, "warehouse")
            if warehouse:
                context["metadata"]["confirmed_warehouse_commitments"] = warehouse.draft.get("commitments")
        async def generate_and_check():
            provider = model or ProposalModel()
            feedback = state["response"]["feedback"] + "\n" + b.evaluation.get("feedback_for_generator", "")
            draft = await GENERATORS[department].generate(provider, context, b.draft, feedback)
            result = await evaluate(provider, context, draft, min(3, b.version + 1))
            result["draft_version"] = b.version + 1
            return draft, result
        draft, result = asyncio.run(generate_and_check())
        # A capacity arbitration cannot disappear by omitting structured terms.
        from services.rfp_approval.models import ApprovalConflict
        with Session(store.engine) as db:
            conflict = db.get(ApprovalConflict, (ticket_id, "volume-vs-capacity"))
            if conflict and department in conflict.department_ids and conflict.status == "request_changes":
                warehouse = store.branch(ticket_id, "warehouse")
                capacity = (warehouse.draft.get("commitments") or {}).get("capacity")
                if not capacity_revision_valid(b.draft, draft, capacity):
                    result["overall_pass"] = False
                    result["feedback_for_generator"] += "\nSupply supported revised volume within the confirmed warehouse capacity and revise the customer cost downward."
                    result["compliance"]["pass"] = False
                    result["compliance"]["violations"].append({"rule_id": "source_grounding", "violation": "Capacity arbitration has not been demonstrably resolved."})
        store.revised(ticket_id, department, token, b.version, draft, result)
        log("revision_evaluation", {"draft": draft}, {"evaluation": result})
        return {"version": b.version + 1}

    graph = StateGraph(ApprovalState)
    graph.add_node("arbitration", arbitration)
    graph.add_node("human_approval", human_approval)
    graph.add_node("record_decision", record)
    graph.add_node("revise", revise)
    graph.add_edge(START, "arbitration")
    graph.add_edge("arbitration", "human_approval")
    graph.add_edge("human_approval", "record_decision")
    graph.add_conditional_edges("record_decision", lambda s: "revise" if s["response"]["decision"] == "request_changes" else END)
    graph.add_edge("revise", "arbitration")
    return graph.compile(checkpointer=saver)


def process_approval(store, ticket_id, department, model=None):
    token = store.claim(ticket_id, department)
    if not token:
        store.complete(ticket_id)
        return {"status": "not_claimed"}
    try:
        with checkpoint_saver(store.engine) as saver:
            graph = department_approval_graph(store, ticket_id, department, token, saver, model)
            config = {"configurable": {"thread_id": f"rfp-{ticket_id}:{department}"}, "recursion_limit": 40}
            saved = graph.get_state(config)
            b = store.branch(ticket_id, department)
            if not saved.values:
                graph.invoke({"ticket_id": ticket_id, "department_id": department}, config)
                saved = graph.get_state(config)
            # Failed nodes replay from their saved checkpoint, not from START.
            if saved.next and not any(task.interrupts for task in saved.tasks):
                graph.invoke(None, config)
                saved = graph.get_state(config)
            b = store.branch(ticket_id, department)
            if b.response and any(task.interrupts for task in saved.tasks):
                graph.invoke(Command(resume=b.response), config)
        store.complete(ticket_id)
        store.release(ticket_id, department, token)
        # A response may arrive after the last checkpoint read while its dispatch
        # sees our still-active lease. Drain that durable response after releasing.
        if store.branch(ticket_id, department).response:
            return process_approval(store, ticket_id, department, model)
        return {"status": "complete" if store.branch(ticket_id, department).approval_status == "approved" else "paused"}
    except Exception:
        store.release(ticket_id, department, token, "Approval processing interrupted. Saved decisions and drafts are retained; retry processing.")
        raise RuntimeError("Approval processing interrupted; saved state retained.") from None
