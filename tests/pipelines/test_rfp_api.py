from tests.pipelines.test_rfp_intake import store as store
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.auth import get_current_user
from services.rfp_intake import router as api


@pytest.fixture
def client(store, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "RAW_ROOT", tmp_path / "uploads")
    monkeypatch.setattr(api, "dispatch", lambda ticket_id: None)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.get_store] = lambda: store
    with TestClient(app) as c:
        yield c, app


def authenticate(app, who="alice"):
    app.dependency_overrides[get_current_user] = lambda: {"user_uuid": who, "is_active": True}


def test_requires_auth(client):
    c, app = client
    assert c.get("/rfp/tickets").status_code == 401
    assert c.post("/rfp/tickets", files={"file": ("x.pdf", b"%PDF-fixture", "application/pdf")}).status_code == 401


@pytest.mark.parametrize(
    "name,body,mime,code",
    [
        ("a.txt", b"%PDF-a", "text/plain", 415),
        ("a.pdf", b"no pdf", "application/pdf", 415),
        ("a.pdf", b"%PDF-" + b"x" * (10 * 1024 * 1024), "application/pdf", 413),
    ],
    ids=["wrong-extension", "invalid-header", "oversized-pdf"],
)
def test_upload_validation(client, name, body, mime, code):
    c, app = client
    authenticate(app)
    assert c.post("/rfp/tickets", files={"file": (name, body, mime)}).status_code == code


def test_quick_upload_stores_pdf_and_pollable_ticket(client, store, tmp_path):
    c, app = client
    authenticate(app)
    response = c.post("/rfp/tickets", files={"file": ("../../request.pdf", b"%PDF-fixture", "application/pdf")})
    assert response.status_code == 202
    d = response.json()
    assert d["status"] == "analyzing" and d["processing_state"] == "queued" and d["original_filename"] == "request.pdf"
    stored = store.owned(d["ticket_id"], "alice")
    assert stored and stored.raw_pdf_path.startswith(str(tmp_path / "uploads"))
    assert open(stored.raw_pdf_path, "rb").read() == b"%PDF-fixture"
    assert c.get("/rfp/tickets/" + d["ticket_id"]).status_code == 200
    assert len(c.get("/rfp/tickets").json()["items"]) == 1
    authenticate(app, "bob")
    assert c.get("/rfp/tickets/" + d["ticket_id"]).status_code == 404
    assert c.post("/rfp/tickets/" + d["ticket_id"] + "/retry").status_code == 404
    assert c.get("/rfp/tickets").json()["items"] == []


def test_queue_failure_saved_and_retriable(client, monkeypatch):
    c, app = client
    authenticate(app)

    def broken(identifier):
        raise RuntimeError("secret broker URL must never leak")

    monkeypatch.setattr(api, "dispatch", broken)
    response = c.post("/rfp/tickets", files={"file": ("request.pdf", b"%PDF-fixture", "application/pdf")})
    assert response.status_code == 202
    d = response.json()
    assert d["processing_state"] == "failed" and d["can_retry"]
    assert "secret" not in response.text
    monkeypatch.setattr(api, "dispatch", lambda identifier: None)
    r = c.post("/rfp/tickets/" + d["ticket_id"] + "/retry")
    assert r.status_code == 202 and r.json()["processing_state"] == "queued"
    assert c.post("/rfp/tickets/" + d["ticket_id"] + "/retry").status_code == 409


def test_malformed_id_and_pagination(client):
    c, app = client
    authenticate(app)
    assert c.get("/rfp/tickets/not-an-id").status_code == 422
    assert c.get("/rfp/tickets?limit=999").status_code == 422
    assert c.get("/rfp/tickets?offset=-1").status_code == 422
