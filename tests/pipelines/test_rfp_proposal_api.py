import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.auth import get_current_user
from services.rfp_generation import router as api
from services.rfp_generation.store import ProposalStore
from tests.pipelines.test_rfp_intake import store as store, ticket, FORMAL, ModelFixture
from data.pipelines.rfp_intake.runner import process_ticket


@pytest.fixture
def setup(store, tmp_path, monkeypatch):
    t = ticket(store, tmp_path)
    process_ticket(store, t.ticket_id, ModelFixture(), lambda _: FORMAL)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.get_store] = lambda: ProposalStore(store.engine)
    calls = []
    monkeypatch.setattr(api, "dispatch", lambda identifier: calls.append(identifier))
    with TestClient(app) as client:
        yield client, app, t.ticket_id, calls


def test_authentication_and_owner_isolation(setup):
    client, app, identifier, calls = setup
    path = f"/rfp/tickets/{identifier}/proposal"
    assert client.post(path).status_code == 401
    app.dependency_overrides[get_current_user] = lambda: {"user_uuid": "bob"}
    assert client.post(path).status_code == 404
    assert client.post(path + "/retry").status_code == 404
    assert calls == []


def test_quick_start_duplicate_and_pollable_queue_failure(setup, monkeypatch):
    client, app, identifier, calls = setup
    app.dependency_overrides[get_current_user] = lambda: {"user_uuid": "alice"}
    path = f"/rfp/tickets/{identifier}/proposal"

    def unavailable(_):
        raise RuntimeError("private broker token")

    monkeypatch.setattr(api, "dispatch", unavailable)
    result = client.post(path)
    assert result.status_code == 202
    body = result.json()
    assert body["status"] == "drafting" and body["proposal"]["can_retry"]
    assert body["proposal"]["state"] == "failed" and "private broker" not in result.text
    assert client.post(path).status_code == 409
    monkeypatch.setattr(api, "dispatch", lambda i: calls.append(i))
    retry = client.post(path + "/retry")
    assert retry.status_code == 202 and retry.json()["proposal"]["state"] == "queued"
    assert calls == [identifier]
    assert client.post(path + "/retry").status_code == 409


def test_invalid_ticket_id(setup):
    client, app, _, _ = setup
    app.dependency_overrides[get_current_user] = lambda: {"user_uuid": "alice"}
    assert client.post("/rfp/tickets/not-a-uuid/proposal").status_code == 422
