"""Dedicated proposal subgraph: department fanout and independent bounded optimization loops."""

import asyncio
import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from .proposal_agents import GENERATORS, ProposalModel, policies, evaluate
from .proposal_schemas import MAX_ATTEMPTS


class DepartmentState(TypedDict, total=False):
    context: dict
    version: int
    draft: dict | None
    evaluation: dict | None


def department_graph(model, checkpoint):
    async def generate(state):
        version = state["version"] + 1
        checkpoint("drafting", version)
        draft = await GENERATORS[state["context"]["department_id"]].generate(
            model,
            state["context"],
            state.get("draft"),
            (state.get("evaluation") or {}).get("feedback_for_generator", ""),
        )
        checkpoint("under_evaluation", version, draft)
        return {"draft": draft, "version": version, "evaluation": None}

    async def review(state):
        result = await evaluate(model, state["context"], state["draft"], state["version"])
        phase = (
            "passed"
            if result["overall_pass"]
            else "needs_human_review"
            if state["version"] >= MAX_ATTEMPTS
            else "revising"
        )
        checkpoint(phase, state["version"], state["draft"], result)
        return {"evaluation": result}

    def route(state):
        if state.get("draft") and not state.get("evaluation"):
            return "evaluate"
        if (state.get("evaluation") or {}).get("overall_pass") or state["version"] >= MAX_ATTEMPTS:
            return END
        return "generate"

    graph = StateGraph(DepartmentState)
    graph.add_node("generate", generate)
    graph.add_node("evaluate", review)
    graph.add_conditional_edges(START, route)
    graph.add_edge("generate", "evaluate")
    graph.add_conditional_edges("evaluate", route)
    return graph.compile()


class ProposalState(TypedDict, total=False):
    contexts: list[dict]
    sections: Annotated[list[dict], operator.add]


def proposal_graph(model, store, ticket_id, token):
    async def section(state):
        context = state["context"]
        dept = context["department_id"]
        latest = store.latest(ticket_id, dept) or {"version": 0, "draft": None, "evaluation": None}
        graph = department_graph(
            model,
            lambda phase, version, draft=None, result=None: store.checkpoint(
                ticket_id, token, dept, phase, version, draft, result
            ),
        )
        result = await graph.ainvoke(
            dict(latest, context=dict(context, policy_sources=policies())), {"recursion_limit": 15}
        )
        return {
            "sections": [
                {
                    "section_id": context["section_id"],
                    "department_id": dept,
                    "draft": result["draft"],
                    "evaluation": result["evaluation"],
                    "attempts": result["version"],
                    "status": "passed" if result["evaluation"]["overall_pass"] else "needs_human_review",
                }
            ]
        }

    graph = StateGraph(ProposalState)
    graph.add_node("route", lambda s: {})
    graph.add_node("department", section)
    graph.add_edge(START, "route")
    graph.add_conditional_edges(
        "route", lambda s: [Send("department", {"context": c}) for c in s["contexts"]], ["department"]
    )
    graph.add_edge("department", END)
    return graph.compile()


def process_proposal(store, ticket_id, model=None):
    claim = store.claim(ticket_id)
    if not claim:
        return {"ticket_id": ticket_id, "status": "not_claimed"}
    token, contexts = claim
    try:
        result = asyncio.run(
            proposal_graph(model or ProposalModel(), store, ticket_id, token).ainvoke(
                {"contexts": contexts, "sections": []}, {"recursion_limit": 20}
            )
        )
        store.finish(ticket_id, token, result["sections"])
        return {"ticket_id": ticket_id, "status": "complete"}
    except Exception:
        store.fail(ticket_id, token)
        raise RuntimeError("Proposal processing interrupted; saved drafts and evaluations are retained.") from None
