"""Runs only against an explicitly configured, disposable PostgreSQL test database."""

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from sqlmodel import create_engine
from data.pipelines.rfp_intake.runner import process_ticket
from services.rfp_intake.models import create_tables
from services.rfp_intake.store import Store
from tests.pipelines.test_rfp_intake import ModelFixture, FORMAL, ticket


@pytest.fixture
def pgstore():
    url = os.getenv("TEST_RFP_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_RFP_DATABASE_URL to a disposable PostgreSQL test database")
    if not url.startswith("postgresql"):
        pytest.fail("PostgreSQL integration must not silently fall back to SQLite")
    engine = create_engine(url, pool_pre_ping=True)
    create_tables(engine)
    yield Store(engine)
    engine.dispose()


def test_postgres_json_and_handoff_survive_new_session(pgstore, tmp_path):
    t = ticket(pgstore, tmp_path, owner="test-" + str(uuid4()))
    result = process_ticket(pgstore, t.ticket_id, ModelFixture(), lambda p: FORMAL)
    assert result["status"] == "intake_complete"
    read = Store(pgstore.engine).details(t.ticket_id, t.owner_id)
    assert read["metadata"]["currency"] == "EUR" and len(read["sections"]) == 2
    assert read["handoff"]["ticket_id"] == t.ticket_id and read["metadata"]["readability_metrics"]["word_count"] > 0
    assert read["created_at"].tzinfo is not None


def test_postgres_concurrent_claim_has_one_winner(pgstore, tmp_path):
    t = ticket(pgstore, tmp_path, owner="test-" + str(uuid4()))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: pgstore.claim(t.ticket_id), range(2)))
    assert sum(value is not None for value in results) == 1
