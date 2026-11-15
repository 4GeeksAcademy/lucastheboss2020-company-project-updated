"""Capture actual model/graph approved and rejected memory cycles using synthetic facts.
Run with: uv run --no-sync --env-file backend/.env python -m scripts.capture_memory_cycles
The existing Qdrant service must be running. No credentials are written to evidence.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from mcps.agent import create_agent_graph
from services.agent_memory.models import Scope
from services.agent_memory.store import MemoryStore

async def capture():
    turns=[]
    with TemporaryDirectory(prefix='trackflow-memory-evidence-') as temporary:
        db=Path(temporary)/'memory.sqlite'
        scope=Scope(company='trackflow',actor='milestone8-evaluator',conversation='approved-cycle')
        async def turn(question, scope):
            # Reopen both graph and SQLite on every turn: no in-process chat history.
            store=MemoryStore(db)
            result=await create_agent_graph(memory_scope=scope,memory_store=store).ainvoke({'question':question})
            record={'conversation':scope.conversation,'question':question,'answer':result['answer'],
                    'recalled':result.get('memory_recalled',[]),
                    'facts_after':store.recall(scope),'audit_after':store.audit(scope)}
            turns.append(record)
            print('Completed evidence turn',len(turns),'facts',len(record['facts_after']),flush=True)
            return record
        first=await turn('The cosmetics client in Spain always wants the monthly report with returns breakdown first, before shipment volume.',scope)
        assert MemoryStore(db).pending(scope), 'Expected a genuine model memory proposal'
        assert not first['facts_after'], 'Proposal must not write an approved fact'
        approved=await turn('Yes, remember that monthly report preference for future conversations.',scope)
        assert len(approved['facts_after'])==1
        future=Scope(company=scope.company,actor=scope.actor,conversation='new-future-session')
        recalled=await turn('How should I order the cosmetics client monthly report in Spain?',future)
        assert recalled['recalled'], 'Approved memory must be retrieved across sessions'
        answer=recalled['answer'].casefold()
        assert 'return' in answer and ('first' in answer or 'before' in answer), 'Answer must reflect remembered ordering'
        rejected_scope=Scope(company=scope.company,actor=scope.actor,conversation='rejected-cycle')
        rejected_first=await turn('The electronics client in Spain always wants the monthly report with shipment volume first, before returns breakdown.',rejected_scope)
        assert MemoryStore(db).pending(rejected_scope)
        before=rejected_first['facts_after']
        rejected=await turn('No, do not remember that preference.',rejected_scope)
        assert rejected['facts_after']==before, 'Rejection must leave approved memory unchanged'
        assert any(event['event']=='approved' for event in rejected['audit_after'])
        assert any(event['event']=='rejected' for event in rejected['audit_after'])
        assert not MemoryStore(db).pending(rejected_scope)
    output={'captured_at':datetime.now(timezone.utc).isoformat(),
            'mode':'Actual configured model and existing MCP LangGraph; actual RAG knowledge path. These report-preference turns do not invoke MCP operational tools.',
            'synthetic_data':True,'cycles_verified':True,'turns':turns}
    path=Path('data/eval/agent-memory-cycles.json'); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n')
    print('VERIFIED approved future-session reuse and rejected unchanged memory:',path,flush=True)

if __name__=='__main__':
    try:
        asyncio.run(capture())
    except Exception as error:
        print('Evidence capture failed:',type(error).__name__,flush=True)
        raise SystemExit(1) from None
