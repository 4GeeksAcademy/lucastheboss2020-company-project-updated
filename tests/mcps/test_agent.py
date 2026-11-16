"""Offline regression: legitimate requests still use the same RAG/MCP graph."""
import asyncio
import time
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
import mcps.agent as agent_module
from services.agent_harness.models import AuthenticatedSession,ResourceGrant
from services.agent_harness.policy import AgentHarness
from services.agent_harness.observability import GuardrailEvents
from services.agent_harness.tools import GetIncidentArgs

class FakeMCPClient:
    def __init__(self): self.calls=[]
    async def get_tools(self,*,server_name):
        self.calls.append(server_name)
        async def get(incident_id): return {'ok':True,'data':{'id':incident_id,'status':'open'}}
        return [StructuredTool.from_function(coroutine=get,name='get_incident',description='Get incident',args_schema=GetIncidentArgs)]

def guard(tmp_path):
    session=AuthenticatedSession(company='trackflow',subject='offline-owner',customer_type='B2C',country='US',expires_at=time.time()+600,
        resources=(ResourceGrant(reference='11111111-1111-4111-8111-111111111111',owner_subject='offline-owner',company='trackflow',country='US',resource_type='incident'),),permissions=('incidents:read',))
    return AgentHarness(session,events=GuardrailEvents(tmp_path/'events.sqlite'))

def test_knowledge_route_uses_existing_rag_and_not_mcp(tmp_path):
    client=FakeMCPClient()
    graph=agent_module.create_agent_graph(mcp_client=client,chat_model=object(),harness=guard(tmp_path),knowledge_query=lambda question:'Grounded knowledge answer')
    result=asyncio.run(graph.ainvoke({'question':'What is the returns policy?'}))
    assert result['route']=='knowledge' and result['answer']=='Grounded knowledge answer' and client.calls==[]

def test_incident_route_discovers_mcp_tools(monkeypatch,tmp_path):
    client=FakeMCPClient();captured={}
    class FakeAgent:
        async def ainvoke(self,state):
            captured['question']=state['messages'][0].content
            await captured['tools'][0].ainvoke({'incident_id':'11111111-1111-4111-8111-111111111111'})
            return {'messages':[AIMessage(content='MCP incident response')]}
    def fake_agent(model,tools,*,prompt): captured['tools']=tools;return FakeAgent()
    monkeypatch.setattr(agent_module,'create_react_agent',fake_agent)
    result=asyncio.run(agent_module.create_agent_graph(mcp_client=client,chat_model=object(),harness=guard(tmp_path)).ainvoke({'question':'Get incident 11111111-1111-4111-8111-111111111111'}))
    assert result['route']=='tools' and result['answer']=='MCP incident response' and client.calls==['trackflow']
    assert [tool.name for tool in captured['tools']]==['get_incident']
    assert captured['question']=='Get incident 11111111-1111-4111-8111-111111111111'
