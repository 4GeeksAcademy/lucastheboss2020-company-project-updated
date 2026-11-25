"""Approval API contracts use persisted fixtures and explicit authenticated actors."""

import copy
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.auth import get_current_user
from services.rfp_approval import router as api
from services.rfp_approval.store import ApprovalStore
from services.rfp_generation.models import ProposalRun
from services.rfp_intake.models import Ticket, DepartmentSection, RFPMetadata
from tests.pipelines.test_rfp_intake import store as store, ticket
from tests.pipelines.test_rfp_proposal import draft


def test_pdf_upload_through_all_three_parts_and_authenticated_final_download(store, tmp_path, monkeypatch):
    """Actual local PDF conversion and HTTP contracts; only models/queue are fixtures."""
    from io import BytesIO
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    from services.rfp_intake import router as intake
    from services.rfp_generation import router as proposal
    from services.rfp_generation.store import ProposalStore
    from data.pipelines.rfp_intake.runner import process_ticket
    from data.pipelines.rfp_intake.proposal_graph import process_proposal
    from data.pipelines.rfp_intake.approval_graph import process_approval
    from tests.pipelines.test_rfp_intake import ModelFixture, FORMAL
    from tests.pipelines.test_rfp_proposal import ProposalFixture

    pdf = PdfWriter()
    page = pdf.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): pdf._add_object(font)})})
    content = DecodedStreamObject()
    content.set_data(f"BT /F1 9 Tf 20 740 Td ({FORMAL}) Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = pdf._add_object(content)
    binary = BytesIO()
    pdf.write(binary)

    app = FastAPI()
    for router in [intake.router, proposal.router, api.router]:
        app.include_router(router)
    approvals = ApprovalStore(store.engine)
    app.dependency_overrides[intake.get_store] = lambda: store
    app.dependency_overrides[proposal.get_store] = lambda: ProposalStore(store.engine)
    app.dependency_overrides[api.get_store] = lambda: approvals
    monkeypatch.setattr(intake, "RAW_ROOT", tmp_path / "actual-pdf-uploads")
    monkeypatch.setattr(intake, "dispatch", lambda identifier: None)
    monkeypatch.setattr(proposal, "dispatch", lambda identifier: None)
    monkeypatch.setattr(api, "dispatch", lambda st, identifier: None)
    monkeypatch.setattr(api, "get_user_by_id", lambda identifier: {"id": identifier, "is_active": True})
    login(app, "alice")
    with TestClient(app) as client:
        uploaded = client.post("/rfp/tickets", files={"file": ("modaviva.pdf", binary.getvalue(), "application/pdf")})
        assert uploaded.status_code == 202 and uploaded.json()["status"] == "analyzing"
        identifier = uploaded.json()["ticket_id"]
        path = f"/rfp/tickets/{identifier}"
        process_ticket(store, identifier, ModelFixture())  # Real MarkItDown/PDF conversion.
        assert client.get(path).json()["status"] == "intake_complete"
        assert client.post(path + "/proposal").status_code == 202
        process_proposal(ProposalStore(store.engine), identifier, ProposalFixture())
        assert client.get(path).json()["status"] == "under_evaluation"
        for department, user in [("warehouse", "ana"), ("reverse", "sofia")]:
            assert client.post(path + "/approvals/reviewers", json={"department_id": department, "user_id": user}).status_code == 200
        assert client.post(path + "/approvals").status_code == 202
        for department in ["warehouse", "reverse"]:
            process_approval(approvals, identifier, department)
        login(app, "sofia")
        assert client.post(path + "/approvals/reverse/resume", json={"decision": "approve", "version": 1}).status_code == 202
        process_approval(approvals, identifier, "reverse")
        assert client.get(path + "/approvals").json()["status"] == "waiting_for_approval"
        assert client.get(path + "/approvals/document").status_code == 409
        login(app, "ana")
        assert client.post(path + "/approvals/warehouse/resume", json={"decision": "approve", "version": 1}).status_code == 202
        process_approval(approvals, identifier, "warehouse")
        assert client.get(path + "/approvals").json()["status"] == "done"
        final = client.get(path + "/approvals/document")
        assert final.status_code == 200 and "ModaViva" in final.text and "EUR" in final.text


@pytest.fixture
def setup(store, tmp_path, monkeypatch):
    """Seed the documented Part 2 handoff; graph behavior is tested separately."""
    t = ticket(store, tmp_path)
    sections = []
    with Session(store.engine) as db:
        row = db.get(Ticket, t.ticket_id)
        row.status = "under_evaluation"
        db.add(row)
        db.add(RFPMetadata(ticket_id=t.ticket_id, client_name="ModaViva", client_country="ES", currency="EUR"))
        for department, owner in [("warehouse", "Ana Whitfield"), ("reverse", "Sofía Ramos")]:
            section = DepartmentSection(ticket_id=t.ticket_id, department_id=department, owner=owner)
            db.add(section)
            sections.append({"section_id": section.section_id, "department_id": department,
                             "draft": draft(department), "evaluation": {"overall_pass": True}, "attempts": 1})
        db.add(ProposalRun(ticket_id=t.ticket_id, state="complete", handoff={"ready_for_part3": True, "sections": sections}))
        db.commit()
    approval_store = ApprovalStore(store.engine)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.get_store] = lambda: approval_store
    users = {name: {"user_uuid": name, "is_active": True} for name in ["alice", "ana", "sofia", "miguel", "bob"]}
    users["inactive"] = {"user_uuid": "inactive", "is_active": False}
    monkeypatch.setattr(api, "get_user_by_id", lambda identifier: users.get(identifier))
    calls = []
    real_dispatch = api.dispatch
    monkeypatch.setattr(api, "dispatch", lambda st, identifier: calls.append(identifier))
    with TestClient(app) as client:
        yield client, app, approval_store, t.ticket_id, calls, real_dispatch


def login(app, actor):
    app.dependency_overrides[get_current_user] = lambda: {"user_uuid": actor, "is_active": True}


def assign(store, identifier):
    store.assign(identifier, "alice", "warehouse", "ana")
    store.assign(identifier, "alice", "reverse", "sofia")


def test_authentication_and_unrelated_account_isolation(setup):
    client, app, store, identifier, calls, _ = setup
    path = f"/rfp/tickets/{identifier}/approvals"
    assert client.get(path).status_code == 401
    assert client.get("/rfp/approvals/inbox").status_code == 401
    assert client.post(path).status_code == 401
    assert client.get(path + "/document").status_code == 401
    assert client.post(path + "/warehouse/resume", json={"decision": "approve", "version": 1}).status_code == 401
    login(app, "bob")
    assert client.get(path).status_code == 404
    assert client.post(path).status_code == 404
    assert client.get(path + "/document").status_code == 404
    assert client.get("/rfp/approvals/inbox").json() == []
    assert calls == []


@pytest.mark.parametrize("user_id", ["missing", "inactive"])
def test_assignment_requires_existing_active_account(setup, user_id):
    client, app, store, identifier, _, _ = setup
    login(app, "alice")
    path = f"/rfp/tickets/{identifier}/approvals"
    result = client.post(path + "/reviewers", json={"department_id": "warehouse", "user_id": user_id})
    assert result.status_code == 422
    assert store.details(identifier, "alice")["reviewers"] == []
    assert client.post(path).status_code == 409


def test_only_creator_assigns_and_starts_while_reviewers_decide_and_see_inbox(setup):
    client, app, store, identifier, calls, _ = setup
    path = f"/rfp/tickets/{identifier}/approvals"
    login(app, "alice")
    for department, user_id in [("warehouse", "ana"), ("reverse", "sofia")]:
        assert client.post(path + "/reviewers", json={"department_id": department, "user_id": user_id}).status_code == 200
    login(app, "ana")
    assert client.get("/rfp/approvals/inbox").json() == [{"ticket_id": identifier, "status": "under_evaluation"}]
    assert client.post(path).status_code == 404
    assert client.post(path + "/reviewers", json={"department_id": "reverse", "user_id": "ana"}).status_code == 404
    login(app, "alice")
    started = client.post(path)
    assert started.status_code == 202 and started.json()["status"] == "waiting_for_approval"
    assert calls == [identifier]
    assert client.post(path + "/warehouse/resume", json={"decision": "approve", "version": 1}).status_code == 403
    login(app, "ana")
    body = client.get(path).json()
    permissions = {s["department_id"]: s["can_decide"] for s in body["sections"]}
    assert permissions == {"warehouse": True, "reverse": False}
    assert client.post(path + "/reverse/resume", json={"decision": "approve", "version": 1}).status_code == 403
    assert client.post(path + "/warehouse/resume", json={"decision": "approve", "version": 1}).status_code == 202
    assert store.branch(identifier, "warehouse").response["actor"] == "ana"


def test_response_schema_stale_versions_and_duplicate_decisions(setup):
    client, app, store, identifier, _, _ = setup
    assign(store, identifier)
    store.start(identifier, "alice")
    login(app, "ana")
    path = f"/rfp/tickets/{identifier}/approvals/warehouse/resume"
    assert client.post(path, json={"decision": "approve", "version": 0}).status_code == 422
    assert client.post(path, json={"decision": "approve", "version": 1, "actor": "alice"}).status_code == 422
    assert client.post(path, json={"decision": "invented", "version": 1}).status_code == 422
    assert client.post(path, json={"decision": "request_changes", "version": 1, "feedback": "   "}).status_code == 422
    assert client.post(path, json={"decision": "reject", "version": 1}).status_code == 422
    assert client.post(path, json={"decision": "approve", "version": 99}).status_code == 409
    result = client.post(path, json={"decision": "request_changes", "version": 1, "feedback": "Clarify the onboarding date."})
    assert result.status_code == 202
    assert client.post(path, json={"decision": "approve", "version": 1}).status_code == 409
    saved = store.branch(identifier, "warehouse")
    assert saved.response["feedback"] == "Clarify the onboarding date."


def test_reviewers_cannot_be_replaced_after_start_and_invalid_ids_are_rejected(setup):
    client, app, store, identifier, _, _ = setup
    assign(store, identifier)
    store.start(identifier, "alice")
    login(app, "alice")
    path = f"/rfp/tickets/{identifier}/approvals/reviewers"
    assert client.post(path, json={"department_id": "warehouse", "user_id": "bob"}).status_code == 409
    assert client.post(path, json={"department_id": "ceo", "user_id": "bob"}).status_code == 422
    assert client.post(path, json={"department_id": "warehouse", "user_id": "ana"}).status_code == 200
    assert client.get("/rfp/tickets/not-a-uuid/approvals").status_code == 422


def test_document_download_is_gated_until_current_versions_are_approved(setup):
    client, app, store, identifier, _, _ = setup
    assign(store, identifier)
    store.start(identifier, "alice")
    login(app, "alice")
    path = f"/rfp/tickets/{identifier}/approvals"
    assert client.get(path + "/document").status_code == 409
    for department, actor in [("warehouse", "ana"), ("reverse", "sofia")]:
        store.respond(identifier, department, actor, "approve", 1)
        branch = store.branch(identifier, department)
        token = store.claim(identifier, department)
        store.apply(identifier, department, token, branch.response)
        store.release(identifier, department, token)
    store.complete(identifier)
    response = client.get(path + "/document")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment;" in response.headers["content-disposition"]
    assert "ModaViva" in response.text and "Currency: EUR" in response.text
    login(app, "bob")
    assert client.get(path + "/document").status_code == 404


def test_queue_failure_preserves_start_and_human_response_for_retry(setup, monkeypatch):
    client, app, store, identifier, _, real_dispatch = setup
    from services.celery_app import app as celery_app

    def unavailable(*args, **kwargs):
        raise RuntimeError("private broker token must not leak")

    assign(store, identifier)
    monkeypatch.setattr(api, "dispatch", real_dispatch)
    monkeypatch.setattr(celery_app, "send_task", unavailable)
    login(app, "alice")
    path = f"/rfp/tickets/{identifier}/approvals"
    response = client.post(path)
    assert response.status_code == 503 and "private broker" not in response.text
    assert store.details(identifier, "alice")["status"] == "waiting_for_approval"
    login(app, "ana")
    response = client.post(path + "/warehouse/resume", json={"decision": "approve", "version": 1})
    assert response.status_code == 503 and "private broker" not in response.text
    assert store.branch(identifier, "warehouse").response["actor"] == "ana"
    monkeypatch.setattr(celery_app, "send_task", lambda *args, **kwargs: None)
    login(app, "alice")
    assert client.post(path).status_code == 202
    assert store.branch(identifier, "warehouse").response["decision"] == "approve"


@pytest.mark.parametrize("trigger,department,arbiter", [
    ("currency-mismatch", "warehouse", "miguel"),
    ("returns-sla-breach", "reverse", "sofia"),
])
def test_arbitration_requires_fixed_arbiter_and_validated_feedback(setup, trigger, department, arbiter):
    client, app, store, identifier, _, _ = setup
    assign(store, identifier)
    store.assign(identifier, "alice", "arbiter", "miguel")
    with Session(store.engine) as db:
        handoff = db.get(ProposalRun, identifier)
        updated = copy.deepcopy(handoff.handoff)
        section = next(s for s in updated["sections"] if s["department_id"] == department)
        if trigger == "currency-mismatch":
            section["draft"]["currency"] = "USD"
        else:
            section["draft"]["returns_turnaround_hours"] = 24
        handoff.handoff = updated
        db.add(handoff)
        db.commit()
    store.start(identifier, "alice")
    path = f"/rfp/tickets/{identifier}/approvals/arbitrate"
    body = {"trigger_id": trigger, "decision": "request_changes", "feedback": "Apply the required business rule."}
    login(app, "alice")
    assert client.post(path, json=body).status_code == 403
    login(app, arbiter)
    assert client.post(path, json={**body, "feedback": ""}).status_code == 422
    assert client.post(path, json={**body, "feedback": "   "}).status_code == 422
    assert client.post(path, json={**body, "decision": "approve"}).status_code == 422
    assert client.post(path, json=body).status_code == 202
    branch = store.branch(identifier, department)
    assert branch.response["actor"] == arbiter
    assert branch.response["decision"] == "request_changes"
    assert "Human arbitration:" in branch.response["feedback"]
    assert client.post(path, json=body).status_code == 409


def test_retry_allows_assigned_reviewers_without_allowing_unrelated_accounts(setup):
    client, app, store, identifier, calls, _ = setup
    assign(store, identifier)
    store.start(identifier, "alice")
    path = f"/rfp/tickets/{identifier}/approvals/retry"
    assert client.post(path).status_code == 401
    login(app, "bob")
    assert client.post(path).status_code == 404
    login(app, "ana")
    response = client.post(path)
    assert response.status_code == 202
    assert response.json()["status"] == "waiting_for_approval"
    assert calls == [identifier]
