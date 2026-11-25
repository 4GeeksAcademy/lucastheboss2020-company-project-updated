"""Crash windows between business commits and graph checkpoints must be replay safe."""

import pytest
from sqlmodel import Session

from data.pipelines.rfp_intake.approval_graph import process_approval
from services.rfp_approval.models import ApprovalBranch, ApprovalConflict
from services.rfp_approval.store import ApprovalError
from services.rfp_intake.models import DepartmentSection
from tests.pipelines.test_rfp_approval import ready as ready, approve
from tests.pipelines.test_rfp_intake import store as store
from tests.pipelines.test_rfp_proposal import ProposalFixture, draft


def crash_after_first_commit(monkeypatch, store, method):
    original = getattr(store, method)
    failed = False

    def call(*args, **kwargs):
        nonlocal failed
        result = original(*args, **kwargs)
        if not failed:
            failed = True
            raise RuntimeError("Simulated crash after business commit, before graph checkpoint")
        return result

    monkeypatch.setattr(store, method, call)


def test_approved_business_commit_survives_missing_graph_checkpoint(ready, monkeypatch):
    identifier, approvals = ready
    process_approval(approvals, identifier, "warehouse")
    approvals.respond(identifier, "warehouse", "ana", "approve", 1)
    crash_after_first_commit(monkeypatch, approvals, "apply")
    with pytest.raises(RuntimeError, match="saved state retained"):
        process_approval(approvals, identifier, "warehouse")
    assert approvals.branch(identifier, "warehouse").approval_status == "approved"
    assert process_approval(approvals, identifier, "warehouse")["status"] == "not_claimed"
    assert approvals.branch(identifier, "warehouse").error is None
    approve(approvals, identifier, "reverse", "sofia")
    review = approvals.details(identifier, "alice")
    assert review["status"] == "done"
    assert review["error"] is None
    records = [event for event in review["trace"] if event["agent"] == "record_decision" and event["department_id"] == "warehouse"]
    assert len(records) == 1


def test_request_changes_commit_replays_record_then_revises_once(ready, monkeypatch):
    identifier, approvals = ready
    process_approval(approvals, identifier, "warehouse")
    approvals.respond(identifier, "warehouse", "ana", "request_changes", 1, "Clarify launch confirmation.")
    crash_after_first_commit(monkeypatch, approvals, "apply")
    provider = ProposalFixture()
    with pytest.raises(RuntimeError):
        process_approval(approvals, identifier, "warehouse", provider)
    assert approvals.branch(identifier, "warehouse").approval_status == "revising"
    process_approval(approvals, identifier, "warehouse", provider)
    branch = approvals.branch(identifier, "warehouse")
    assert branch.version == 2 and branch.revision_count == 1 and branch.approval_status == "pending"
    revisions = [event for event in approvals.details(identifier, "alice")["trace"] if event["agent"] == "revise"]
    assert len(revisions) == 1


def test_revision_commit_replay_does_not_generate_or_increment_again(ready, monkeypatch):
    identifier, approvals = ready
    process_approval(approvals, identifier, "warehouse")
    approvals.respond(identifier, "warehouse", "ana", "request_changes", 1, "Clarify launch confirmation.")
    crash_after_first_commit(monkeypatch, approvals, "revised")
    provider = ProposalFixture()
    with pytest.raises(RuntimeError):
        process_approval(approvals, identifier, "warehouse", provider)
    assert approvals.branch(identifier, "warehouse").version == 2
    calls_after_commit = list(provider.calls)
    process_approval(approvals, identifier, "warehouse", provider)
    assert provider.calls == calls_after_commit
    branch = approvals.branch(identifier, "warehouse")
    assert branch.version == 2 and branch.revision_count == 1 and branch.approval_status == "pending"
    approve(approvals, identifier, "warehouse", "ana")
    approve(approvals, identifier, "reverse", "sofia")
    assert approvals.details(identifier, "alice")["document"]["sections"]["warehouse"] == 2


def test_final_document_commit_is_idempotent_after_worker_crash(ready, monkeypatch):
    identifier, approvals = ready
    approve(approvals, identifier, "warehouse", "ana")
    process_approval(approvals, identifier, "reverse")
    approvals.respond(identifier, "reverse", "sofia", "approve", 1)
    crash_after_first_commit(monkeypatch, approvals, "complete")
    with pytest.raises(RuntimeError):
        process_approval(approvals, identifier, "reverse")
    original = approvals.details(identifier, "alice")["document"]
    assert original
    process_approval(approvals, identifier, "reverse")
    review = approvals.details(identifier, "alice")
    assert review["status"] == "done" and review["document"] == original
    assert approvals.branch(identifier, "reverse").error is None
    assert review["error"] is None
    assert sum(event["agent"] == "final_document_synthesizer" for event in review["trace"]) == 1


def test_invalid_currency_exhausts_arbitration_revisions_and_requires_rejection(ready):
    identifier, approvals = ready
    approve(approvals, identifier, "reverse", "sofia")
    with Session(approvals.engine) as db:
        branch = db.get(ApprovalBranch, (identifier, "warehouse"))
        branch.draft = dict(branch.draft, currency="USD", content=branch.draft["content"].replace("EUR", "USD"))
        db.add(branch)
        db.commit()
    process_approval(approvals, identifier, "warehouse")

    class StillWrongCurrency(ProposalFixture):
        def generate(self, role, payload, schema):
            result = super().generate(role, payload, schema)
            if schema.__name__ == "ProposalDraft":
                result = dict(result, currency="USD", content=result["content"].replace("EUR", "USD"))
            return result

    provider = StillWrongCurrency()
    for round_number in range(1, 4):
        approvals.resolve(identifier, "miguel", "currency-mismatch", "request_changes", "Spain quotations must use EUR.")
        process_approval(approvals, identifier, "warehouse", provider)
        branch = approvals.branch(identifier, "warehouse")
        assert branch.version == round_number + 1 and branch.revision_count == round_number
        assert not branch.evaluation["overall_pass"]
        assert approvals.branch(identifier, "reverse").approved_version == 1
    with pytest.raises(ApprovalError, match="limit"):
        approvals.resolve(identifier, "miguel", "currency-mismatch", "request_changes", "Try another correction.")
    with pytest.raises(ApprovalError):
        approvals.respond(identifier, "warehouse", "ana", "approve", 4)
    calls_at_limit = len(provider.calls)
    process_approval(approvals, identifier, "warehouse", provider)
    assert len(provider.calls) == calls_at_limit
    review = approvals.details(identifier, "alice")
    assert review["blocked"] and review["document"] is None and review["status"] == "waiting_for_approval"
    approvals.resolve(identifier, "miguel", "currency-mismatch", "reject", "Required currency remains unresolved after three revisions.")
    process_approval(approvals, identifier, "warehouse", provider)
    assert approvals.branch(identifier, "warehouse").approval_status == "rejected"
    assert approvals.details(identifier, "alice")["document"] is None


def test_capacity_dependency_revision_refreshes_decided_conflict(ready):
    identifier, approvals = ready
    capacity = {"value": 100, "unit": "orders", "period": "month", "evidence": "Confirmed capacity: 100 orders per month."}
    volume = {"value": 200, "unit": "orders", "period": "month", "evidence": "Requested volume: 200 orders per month."}
    with Session(approvals.engine) as db:
        warehouse = db.get(ApprovalBranch, (identifier, "warehouse"))
        warehouse.draft = dict(warehouse.draft, commitments={"capacity": capacity})
        db.add(warehouse)
        db.add(DepartmentSection(ticket_id=identifier, department_id="lastmile", owner="Carlos Vega"))
        db.add(ApprovalBranch(ticket_id=identifier, department_id="lastmile", version=1,
                              draft=dict(draft("lastmile"), commitments={"volume": volume}), evaluation={"overall_pass": True}))
        db.commit()
    approvals.arbitrate(identifier)
    approvals.resolve(identifier, "miguel", "volume-vs-capacity", "request_changes", "Use confirmed warehouse capacity.")
    with Session(approvals.engine) as db:
        conflict = db.get(ApprovalConflict, (identifier, "volume-vs-capacity"))
        assert conflict.status == "request_changes"
        assert conflict.versions == {"warehouse": 1, "lastmile": 1}
        warehouse = db.get(ApprovalBranch, (identifier, "warehouse"))
        warehouse.version = 2
        warehouse.draft = dict(warehouse.draft, commitments={"capacity": dict(capacity, value=50, evidence="Confirmed capacity: 50 orders per month.")})
        db.add(warehouse)
        db.commit()
    approvals.arbitrate(identifier)
    with Session(approvals.engine) as db:
        refreshed = db.get(ApprovalConflict, (identifier, "volume-vs-capacity"))
        assert refreshed.status == "pending"
        assert refreshed.versions == {"warehouse": 2, "lastmile": 1}
        assert "50 orders/month" in refreshed.resolution
    assert approvals.branch(identifier, "lastmile").version == 1
