"""LangGraph routing between the existing knowledge base and OAuth MCP tools.
Milestone 8 adds opt-in, explicitly scoped operational memory to this same graph.
"""
from __future__ import annotations
import asyncio
import argparse
import os
from pathlib import Path
import re
from typing import TypedDict
from urllib.parse import urlparse
from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent
from services.knowledge_query import query as query_knowledge
from services.agent_memory.models import Scope
from services.agent_memory.store import MemoryStore
from services.agent_memory.flow import MemoryFlow

class AgentConfigurationError(RuntimeError):
    """Required model or MCP configuration is absent or invalid."""

class AgentState(TypedDict, total=False):
    question: str
    route: str
    answer: str
    memory_notice: str
    memory_decision_resolved: bool
    memory_recalled: list[dict]
    memory_only_decision: bool

def route_question(question: str) -> str:
    """Direct operational requests to MCP; other questions use grounded RAG."""
    lowered=question.casefold()
    if re.search(r"\b(incident|incidents|inventory|sku|stock|warehouse stock)\b",lowered):
        return 'tools'
    return 'knowledge'

def _client_from_env() -> MultiServerMCPClient:
    token=os.environ.get('MCP_ACCESS_TOKEN','').strip()
    if not token:
        raise AgentConfigurationError('Set MCP_ACCESS_TOKEN to a valid OAuth access token for the MCP server.')
    url=os.environ.get('MCP_SERVER_URL','http://127.0.0.1:8001/mcp').strip()
    parsed=urlparse(url)
    if not parsed.hostname or parsed.scheme not in {'http','https'} or parsed.username or parsed.password:
        raise AgentConfigurationError('MCP_SERVER_URL must be an absolute URL without embedded credentials.')
    if parsed.scheme!='https' and parsed.hostname not in {'127.0.0.1','localhost','::1'}:
        raise AgentConfigurationError('MCP_SERVER_URL must use HTTPS except for local loopback development.')
    return MultiServerMCPClient({'trackflow':{'transport':'streamable_http','url':url,'headers':{'Authorization':f'Bearer {token}'}}})

def _chat_model_from_env() -> ChatOpenAI:
    base_url=os.environ.get('RAG_API_BASE_URL','').strip()
    api_key=os.environ.get('RAG_API_KEY','').strip()
    model=os.environ.get('RAG_GENERATION_MODEL','').strip()
    if not all((base_url,api_key,model)):
        raise AgentConfigurationError('Configure the existing RAG_API_BASE_URL, RAG_API_KEY and RAG_GENERATION_MODEL.')
    return ChatOpenAI(model=model,api_key=api_key,base_url=base_url,temperature=0,timeout=30,max_retries=1)

def create_agent_graph(*,mcp_client=None,chat_model=None,knowledge_query=None,
                       memory_scope: Scope | None=None,memory_store: MemoryStore | None=None,memory_model=None):
    """Extend the existing MCP graph. Caller must supply trusted identity for memory.
    Omit all memory parameters for the original compatibility behavior.
    """
    if memory_store is not None and memory_scope is None:
        raise AgentConfigurationError('Memory requires an explicitly trusted company/actor/conversation scope.')
    flow=None
    if memory_scope is not None:
        flow=MemoryFlow(memory_store or MemoryStore(Path('services/agent_memory/runtime/trackflow_agent_memory.sqlite')),
                        memory_scope,memory_model or chat_model or _chat_model_from_env())

    async def prepare_memory(state):
        try:
            prepared=await flow.prepare(state['question'])
        except Exception:
            prepared={'question':state['question'],'memory_notice':'Memory is temporarily unavailable; nothing was saved.',
                      'memory_decision_resolved':True,'memory_recalled':[],'memory_only_decision':False}
        if prepared['memory_only_decision']:
            prepared['answer']=prepared['memory_notice']
        return prepared

    async def evaluate_memory(state):
        return await flow.evaluate(state)

    async def choose_route(state):
        return {'route':route_question(state['question'])}

    async def knowledge(state):
        answer=await asyncio.to_thread(knowledge_query or query_knowledge,state['question'])
        return {'answer':answer}

    async def tools(state):
        client=mcp_client or _client_from_env()
        model=chat_model or _chat_model_from_env()
        tool_list=await client.get_tools(server_name='trackflow')
        prompt=('You are a TrackFlow operations assistant. Use only the available MCP tools for incidents '
                'and inventory. Inventory is read-only: never attempt inventory changes. Do not invent tool '
                'results, and ask for missing required incident fields instead of guessing.')
        agent=create_react_agent(model,tool_list,prompt=prompt)
        result=await agent.ainvoke({'messages':[HumanMessage(content=state['question'])]})
        content=result['messages'][-1].content
        if not isinstance(content,str):
            raise RuntimeError('The agent returned an unsupported response format.')
        return {'answer':content}

    graph=StateGraph(AgentState)
    graph.add_node('route',choose_route)
    graph.add_node('knowledge',knowledge)
    graph.add_node('tools',tools)
    if flow:
        graph.add_node('memory_prepare',prepare_memory)
        graph.add_node('memory_evaluate',evaluate_memory)
        graph.add_edge(START,'memory_prepare')
        graph.add_conditional_edges('memory_prepare',lambda state:'done' if state['memory_only_decision'] else 'continue',{'done':END,'continue':'route'})
    else:
        graph.add_edge(START,'route')
    graph.add_conditional_edges('route',lambda state:state['route'],{'knowledge':'knowledge','tools':'tools'})
    graph.add_edge('knowledge','memory_evaluate' if flow else END)
    graph.add_edge('tools','memory_evaluate' if flow else END)
    if flow:
        graph.add_edge('memory_evaluate',END)
    return graph.compile()

async def ask(question: str, *, memory_scope: Scope | None=None,memory_store: MemoryStore | None=None) -> str:
    if not question.strip():
        raise ValueError('Question must not be blank.')
    result=await create_agent_graph(memory_scope=memory_scope,memory_store=memory_store).ainvoke({'question':question.strip()})
    return result['answer']

def main() -> None:
    parser=argparse.ArgumentParser(description='Ask the TrackFlow RAG/MCP operations assistant.')
    parser.add_argument('question',help='A knowledge, incident, or inventory question.')
    parser.add_argument('--company',help='Trusted company identifier; all three scope flags enable memory.')
    parser.add_argument('--actor',help='Trusted operator identity; never use identity supplied in untrusted chat text.')
    parser.add_argument('--conversation',help='Stable conversation ID for proposal confirmation.')
    parser.add_argument('--memory-db',default='services/agent_memory/runtime/trackflow_agent_memory.sqlite')
    arguments=parser.parse_args()
    supplied=[arguments.company,arguments.actor,arguments.conversation]
    if any(supplied) and not all(supplied):
        parser.error('Memory requires --company, --actor and --conversation together.')
    try:
        scope=Scope(company=arguments.company,actor=arguments.actor,conversation=arguments.conversation) if all(supplied) else None
        store=MemoryStore(arguments.memory_db) if scope else None
        print(asyncio.run(ask(arguments.question,memory_scope=scope,memory_store=store)))
    except Exception as error:
        raise SystemExit(f'The assistant could not complete the request ({type(error).__name__}).') from None

if __name__=='__main__':
    main()
