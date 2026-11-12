"""LangGraph routing between the existing knowledge base and OAuth MCP tools."""

from __future__ import annotations

import asyncio
import argparse
import os
import re
from typing import TypedDict
from urllib.parse import urlparse

from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent

from services.knowledge_query import query as query_knowledge


class AgentConfigurationError(RuntimeError):
    """The agent is missing an OAuth token or an approved model configuration."""


class AgentState(TypedDict, total=False):
    question: str
    route: str
    answer: str


def route_question(question: str) -> str:
    """Direct operational requests to MCP; other questions use grounded RAG."""
    lowered = question.casefold()
    if re.search(r"\b(incident|incidents|inventory|sku|stock|warehouse stock)\b", lowered):
        return "tools"
    return "knowledge"


def _client_from_env() -> MultiServerMCPClient:
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    if not token:
        raise AgentConfigurationError("Set MCP_ACCESS_TOKEN to a valid OAuth access token for the MCP server.")
    url = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8001/mcp").strip()
    parsed = urlparse(url)
    if not parsed.hostname or parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        raise AgentConfigurationError("MCP_SERVER_URL must be an absolute URL without embedded credentials.")
    if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise AgentConfigurationError("MCP_SERVER_URL must use HTTPS except for local loopback development.")
    return MultiServerMCPClient({
        "trackflow": {
            "transport": "streamable_http",
            "url": url,
            "headers": {"Authorization": f"Bearer {token}"},
        }
    })


def _chat_model_from_env() -> ChatOpenAI:
    base_url = os.environ.get("RAG_API_BASE_URL", "").strip()
    api_key = os.environ.get("RAG_API_KEY", "").strip()
    model = os.environ.get("RAG_GENERATION_MODEL", "").strip()
    if not all((base_url, api_key, model)):
        raise AgentConfigurationError("Configure the existing RAG_API_BASE_URL, RAG_API_KEY and RAG_GENERATION_MODEL.")
    return ChatOpenAI(model=model, api_key=api_key, base_url=base_url, temperature=0, timeout=30, max_retries=1)


def create_agent_graph(*, mcp_client=None, chat_model=None, knowledge_query=None):
    """Create a graph with injectable local test doubles and no direct incident API access."""
    async def choose_route(state: AgentState) -> dict:
        return {"route": route_question(state["question"])}

    async def knowledge(state: AgentState) -> dict:
        answer = await asyncio.to_thread(knowledge_query or query_knowledge, state["question"])
        return {"answer": answer}

    async def tools(state: AgentState) -> dict:
        client = mcp_client or _client_from_env()
        model = chat_model or _chat_model_from_env()
        tool_list = await client.get_tools(server_name="trackflow")
        agent = create_react_agent(
            model,
            tool_list,
            prompt=(
                "You are a TrackFlow operations assistant. Use only the available MCP tools for incidents "
                "and inventory. Inventory is read-only: never attempt inventory changes. Do not invent tool "
                "results, and ask for missing required incident fields instead of guessing."
            ),
        )
        result = await agent.ainvoke({"messages": [HumanMessage(content=state["question"])]})
        content = result["messages"][-1].content
        if not isinstance(content, str):
            raise RuntimeError("The agent returned an unsupported response format.")
        return {"answer": content}

    graph = StateGraph(AgentState)
    graph.add_node("route", choose_route)
    graph.add_node("knowledge", knowledge)
    graph.add_node("tools", tools)
    graph.add_edge(START, "route")
    graph.add_conditional_edges("route", lambda state: state["route"], {"knowledge": "knowledge", "tools": "tools"})
    graph.add_edge("knowledge", END)
    graph.add_edge("tools", END)
    return graph.compile()


async def ask(question: str) -> str:
    if not question.strip():
        raise ValueError("Question must not be blank.")
    result = await create_agent_graph().ainvoke({"question": question.strip()})
    return result["answer"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the TrackFlow RAG/MCP operations assistant.")
    parser.add_argument("question", help="A knowledge, incident, or inventory question.")
    arguments = parser.parse_args()
    try:
        print(asyncio.run(ask(arguments.question)))
    except Exception as error:
        raise SystemExit(f"The assistant could not complete the request ({type(error).__name__}).") from None


if __name__ == "__main__":
    main()