"""Transactional, scoped SQLite memory. No raw user messages or credentials are stored."""
from __future__ import annotations
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
from uuid import uuid4
from .models import Candidate, Decision, Scope, fact_key, fingerprint, validate_candidate

class MemoryStore:
    def __init__(self, path: str | Path, *, clock=time.time, max_facts=100):
        if not isinstance(max_facts,int) or not 1 <= max_facts <= 100:
            raise ValueError("max_facts must be between 1 and 100")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self.max_facts = max_facts
        with self._tx() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS proposals (
              id TEXT PRIMARY KEY, company TEXT NOT NULL, actor TEXT NOT NULL,
              conversation TEXT NOT NULL, version INTEGER NOT NULL, candidate TEXT NOT NULL,
              source_ref TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL,
              status TEXT NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS one_pending ON proposals(company,actor) WHERE status='pending';
            CREATE TABLE IF NOT EXISTS facts (
              company TEXT NOT NULL, actor TEXT NOT NULL, key TEXT NOT NULL,
              candidate TEXT NOT NULL, proposal_id TEXT NOT NULL, authorized_by TEXT NOT NULL,
              updated REAL NOT NULL, expires REAL NOT NULL,
              PRIMARY KEY(company,actor,key));
            CREATE TABLE IF NOT EXISTS audit (
              seq INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT NOT NULL, actor TEXT NOT NULL,
              conversation TEXT NOT NULL, proposal_id TEXT NOT NULL, version INTEGER NOT NULL,
              event TEXT NOT NULL, source_ref TEXT NOT NULL, timestamp REAL NOT NULL, candidate TEXT NOT NULL);
            """)

    @contextmanager
    def _tx(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _event(self, db, scope, p, event, source_ref):
        db.execute("INSERT INTO audit(company,actor,conversation,proposal_id,version,event,source_ref,timestamp,candidate) VALUES(?,?,?,?,?,?,?,?,?)",
                   (scope.company,scope.actor,scope.conversation,p['id'],p['version'],event,source_ref,self.clock(),p['candidate']))
        db.execute("DELETE FROM audit WHERE company=? AND actor=? AND seq NOT IN (SELECT seq FROM audit WHERE company=? AND actor=? ORDER BY seq DESC LIMIT 10000)",(scope.company,scope.actor,scope.company,scope.actor))
        db.execute("DELETE FROM proposals WHERE company=? AND actor=? AND status!='pending' AND id NOT IN (SELECT id FROM proposals WHERE company=? AND actor=? ORDER BY created DESC,id LIMIT 10000)",(scope.company,scope.actor,scope.company,scope.actor))

    def _cleanup(self, db, scope):
        now = self.clock()
        rows = db.execute("SELECT * FROM proposals WHERE company=? AND actor=? AND status='pending' AND expires<=?",(scope.company,scope.actor,now)).fetchall()
        for p in rows:
            self._event(db,Scope(company=p['company'],actor=p['actor'],conversation=p['conversation']),p,'expired',p['source_ref'])
            db.execute("UPDATE proposals SET status='expired' WHERE id=?",(p['id'],))
        db.execute("DELETE FROM facts WHERE company=? AND actor=? AND expires<=?",(scope.company,scope.actor,now))
        # Audit retains a year, with a hard cap of 10,000 events per principal.
        db.execute("DELETE FROM audit WHERE company=? AND actor=? AND timestamp<?",(scope.company,scope.actor,now-365*86400))
        db.execute("DELETE FROM audit WHERE company=? AND actor=? AND seq NOT IN (SELECT seq FROM audit WHERE company=? AND actor=? ORDER BY seq DESC LIMIT 10000)",(scope.company,scope.actor,scope.company,scope.actor))
        db.execute("DELETE FROM proposals WHERE company=? AND actor=? AND status!='pending' AND created<?",(scope.company,scope.actor,now-365*86400))

        db.execute("DELETE FROM proposals WHERE company=? AND actor=? AND status!='pending' AND id NOT IN (SELECT id FROM proposals WHERE company=? AND actor=? ORDER BY created DESC,id LIMIT 10000)",(scope.company,scope.actor,scope.company,scope.actor))

    def cleanup(self, scope: Scope):
        with self._tx() as db:
            self._cleanup(db,scope)

    def pending(self, scope: Scope):
        with self._tx() as db:
            self._cleanup(db,scope)
            row = db.execute("SELECT * FROM proposals WHERE company=? AND actor=? AND status='pending'",(scope.company,scope.actor)).fetchone()
            return dict(row) if row else None

    def propose(self, scope: Scope, candidate: Candidate, source_message: str):
        validate_candidate(candidate,source_message)
        with self._tx() as db:
            self._cleanup(db,scope)
            if db.execute("SELECT 1 FROM proposals WHERE company=? AND actor=? AND status='pending'",(scope.company,scope.actor)).fetchone():
                return None
            old = db.execute("SELECT candidate FROM facts WHERE company=? AND actor=? AND key=?",(scope.company,scope.actor,fact_key(candidate))).fetchone()
            if old and json.loads(old['candidate'])['fact'].strip().casefold()==candidate.fact.strip().casefold():
                return None
            p = dict(id=str(uuid4()),version=1,source_ref=fingerprint(source_message),candidate=candidate.model_dump_json())
            now=self.clock()
            db.execute("INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?,?,?)",(p['id'],scope.company,scope.actor,scope.conversation,1,candidate.model_dump_json(),p['source_ref'],now,now+600,'pending'))
            self._event(db,scope,p,'proposed',p['source_ref'])
            return dict(p,candidate=candidate.model_dump(),expires=now+600,replaces=json.loads(old['candidate'])['fact'] if old else None)

    def resolve(self, scope: Scope, decision: Decision, message: str):
        with self._tx() as db:
            self._cleanup(db,scope)
            p=db.execute("SELECT * FROM proposals WHERE id=? AND company=? AND actor=? AND status='pending'",(decision.proposal_id,scope.company,scope.actor)).fetchone()
            if not p or p['version']!=decision.version:
                return 'stale'
            label=decision.label if decision.confidence>=0.9 else 'uncertain'
            if p['conversation']!=scope.conversation:
                label='unrelated'
            if label=='edit':
                try:
                    if decision.edited_proposal is None: raise ValueError('missing edit')
                    candidate=validate_candidate(decision.edited_proposal,message)
                except ValueError:
                    label='rejected_invalid_edit'
                else:
                    self._event(db,scope,p,'edited',fingerprint(message))
                    db.execute("UPDATE proposals SET version=version+1,candidate=?,source_ref=?,created=?,expires=? WHERE id=?",(candidate.model_dump_json(),fingerprint(message),self.clock(),self.clock()+600,p['id']))
                    revised=dict(p); revised['version']+=1; revised['candidate']=candidate.model_dump_json()
                    self._event(db,scope,revised,'proposed',fingerprint(message))
                    return 'edited'
            if label=='approve':
                candidate=validate_candidate(Candidate.model_validate_json(p['candidate']))
                ttl=7*86400 if candidate.kind=='recurring_incident' else 90*86400
                self._event(db,scope,p,'approved',fingerprint(message))
                db.execute("INSERT INTO facts VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(company,actor,key) DO UPDATE SET candidate=excluded.candidate,proposal_id=excluded.proposal_id,authorized_by=excluded.authorized_by,updated=excluded.updated,expires=excluded.expires",(scope.company,scope.actor,fact_key(candidate),candidate.model_dump_json(),p['id'],scope.actor,self.clock(),self.clock()+ttl))
                db.execute("DELETE FROM facts WHERE company=? AND actor=? AND key NOT IN (SELECT key FROM facts WHERE company=? AND actor=? ORDER BY updated DESC,key LIMIT ?)",(scope.company,scope.actor,scope.company,scope.actor,self.max_facts))
                outcome='approved'
            else:
                outcome='rejected' if label=='reject' else label
                self._event(db,scope,p,outcome,fingerprint(message))
            db.execute("UPDATE proposals SET status=? WHERE id=?",(outcome,p['id']))
            return outcome

    def recall(self, scope: Scope, question: str = '', *, limit=8):
        with self._tx() as db:
            self._cleanup(db,scope)
            rows=db.execute("SELECT * FROM facts WHERE company=? AND actor=? ORDER BY updated DESC,key",(scope.company,scope.actor)).fetchall()
            # Small structured corpus: bounded lexical selection, not full conversation history.
            terms=set(question.casefold().split())
            scored=[]
            for row in rows:
                candidate=Candidate.model_validate_json(row['candidate'])
                hay=(candidate.entity+' '+candidate.fact+' '+candidate.country).casefold()
                score=sum(term in hay for term in terms if len(term)>2)
                if not question or score:
                    scored.append((score,dict(candidate.model_dump(),proposal_id=row['proposal_id'],authorized_by=row['authorized_by'],expires=row['expires'])))
            scored.sort(key=lambda item:item[0],reverse=True)
            return [item for _,item in scored[:max(0,min(limit,8))]]

    def audit(self, scope: Scope):
        with self._tx() as db:
            self._cleanup(db,scope)
            return [dict(r) for r in db.execute("SELECT * FROM audit WHERE company=? AND actor=? ORDER BY seq",(scope.company,scope.actor))]
