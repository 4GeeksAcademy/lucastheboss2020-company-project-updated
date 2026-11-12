"""Offline tests for LangGraph knowledge-versus-MCP routing."""

import asyncio

from langchain_core.messages import AIMessage

import mcps.agent as agent_module


class FakeMCPClient:
    def __init__(self):
        self.calls = []

    async def get_tools(self, *, server_name):
        self.calls.append(server_name)
        return ["mcp-tool-placeholder"]


def test_knowledge_route_uses_existing_rag_and_not_mcp():
    client = FakeMCPClient()
    graph = agent_module.create_agent_graph(
        mcp_client=client,
        chat_model=object(),
        knowledge_query=lambda question: "Grounded knowledge answer",
    )
    result = asyncio.run(graph.ainvoke({"question": "What is the returns policy?"}))
    assert result["route"] == "knowledge"
    assert result["answer"] == "Grounded knowledge answer"
    assert client.calls == []


def test_incident_route_discovers_mcp_tools(monkeypatch):
    client = FakeMCPClient()
    captured = {}

    class FakeAgent:
        async def ainvoke(self, state):
            captured["question"] = state["messages"][0].content
            return {"messages": [AIMessage(content="MCP incident response")]}

    def fake_agent(model, tools, *, prompt):
        captured["tools"] = tools
        return FakeAgent()

    monkeypatch.setattr(agent_module, "create_react_agent", fake_agent)
    graph = agent_module.create_agent_graph(mcp_client=client, chat_model=object())
    result = asyncio.run(graph.ainvoke({"question": "Get incident 123"}))
    assert result["route"] == "tools"
    assert result["answer"] == "MCP incident response"
    assert client.calls == ["trackflow"]
    assert captured["tools"] == ["mcp-tool-placeholder"]
    assert captured["question"] == "Get incident 123"