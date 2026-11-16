"""Privacy-safe durable guardrail events and test-session summaries."""
from __future__ import annotations
import json
from pathlib import Path
import re
import sqlite3
import time

class GuardrailEvents:
    def __init__(self,path='services/agent_harness/runtime/guardrails.sqlite'):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        with self._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp REAL NOT NULL, test_session TEXT NOT NULL, request_id TEXT NOT NULL, failure_type TEXT NOT NULL, guard TEXT NOT NULL, action TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS guard_session ON events(test_session,id)')

    def _connect(self):
        return sqlite3.connect(self.path,timeout=15)

    def record(self,*,test_session,request_id,failure_type,guard,action):
        if failure_type not in {'structural','content','security'} or action not in {'block','redirect'}:
            raise ValueError('Invalid guard event')
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',test_session) or not re.fullmatch(r'[a-z0-9_-]{1,64}',guard):
            raise ValueError('Invalid event metadata')
        # No prompt, answer, subject, reference, token, or payload column exists.
        with self._connect() as db:
            db.execute('INSERT INTO events(timestamp,test_session,request_id,failure_type,guard,action) VALUES(?,?,?,?,?,?)',(time.time(),test_session,request_id,failure_type,guard,action))
            db.execute('DELETE FROM events WHERE timestamp<?',(time.time()-90*86400,))
            db.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 100000)')

    def summary(self,test_session):
        with self._connect() as db:
            rows=db.execute('SELECT failure_type,guard,action,count(*) FROM events WHERE test_session=? GROUP BY failure_type,guard,action ORDER BY failure_type,guard,action',(test_session,)).fetchall()
        return {'test_session':test_session,'total':sum(r[3] for r in rows),'counts':[{'failure_type':r[0],'guard':r[1],'action':r[2],'count':r[3]} for r in rows]}
