"""Crash windows between business commits and graph checkpoints must be replay safe."""

import pytest

from data.pipelines.rfp_intake.approval_graph import process_approval
from tests.pipelines.test_rfp_approval import ready as ready, approve
from tests.pipelines.test_rfp_intake import store as store
from tests.pipelines.test_rfp_proposal import ProposalFixture


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
    approve(approvals, identifier, "reverse", "sofia")
    review = approvals.details(identifier, "alice")
    assert review["status"] == "done"
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
    assert sum(event["agent"] == "final_document_synthesizer" for event in review["trace"]) == 1
