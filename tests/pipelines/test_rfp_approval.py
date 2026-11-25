"""Reproducible Parts 1→3 with explicit model fixtures and simulated human resumes."""
import copy
import pytest
from sqlmodel import Session, select, create_engine
from tests.pipelines.test_rfp_intake import store as store, ticket, ModelFixture, FORMAL
from tests.pipelines.test_rfp_proposal import ProposalFixture, draft
from data.pipelines.rfp_intake.runner import process_ticket
from data.pipelines.rfp_intake.proposal_graph import process_proposal
from data.pipelines.rfp_intake.approval_graph import process_approval, checkpoint_saver, department_approval_graph
from data.pipelines.rfp_intake.approval_rules import conflicts
from services.rfp_generation.store import ProposalStore
from services.rfp_approval.store import ApprovalStore, ApprovalError
from services.rfp_approval.models import ApprovalBranch, ApprovalTrace, FinalDocument
from services.rfp_intake.models import Ticket, create_tables
from services.rfp_intake.store import Store


def prepared(intake, tmp_path):
    t = ticket(intake, tmp_path)
    process_ticket(intake, t.ticket_id, ModelFixture(), lambda _: FORMAL)
    ProposalStore(intake.engine).start(t.ticket_id, "alice")
    process_proposal(ProposalStore(intake.engine), t.ticket_id, ProposalFixture())
    approvals = ApprovalStore(intake.engine)
    approvals.assign(t.ticket_id, "alice", "warehouse", "ana")
    approvals.assign(t.ticket_id, "alice", "reverse", "sofia")
    approvals.assign(t.ticket_id, "alice", "arbiter", "miguel")
    approvals.start(t.ticket_id, "alice")
    return t.ticket_id, approvals


@pytest.fixture
def ready(store, tmp_path):
    return prepared(store, tmp_path)


def approve(approvals, identifier, department, actor):
    b = approvals.branch(identifier, department)
    approvals.respond(identifier, department, actor, "approve", b.version)
    return process_approval(approvals, identifier, department, ProposalFixture())


def test_parallel_interrupt_resume_full_flow(ready):
    identifier, approvals = ready
    process_approval(approvals, identifier, "warehouse")
    process_approval(approvals, identifier, "reverse")
    with checkpoint_saver(approvals.engine) as saver:
        graph = department_approval_graph(approvals, identifier, "warehouse", "unused", saver)
        snapshot = graph.get_state({"configurable": {"thread_id": f"rfp-{identifier}:warehouse"}})
        assert any(t.interrupts for t in snapshot.tasks)
    assert approve(approvals, identifier, "reverse", "sofia")["status"] == "complete"
    details = approvals.details(identifier, "alice")
    assert details["status"] == "waiting_for_approval" and details["document"] is None
    assert approvals.branch(identifier, "warehouse").approval_status == "pending"
    assert approvals.branch(identifier, "reverse").approval_status == "approved"
    assert approve(approvals, identifier, "warehouse", "ana")["status"] == "complete"
    details = approvals.details(identifier, "alice")
    assert details["status"] == "done"
    assert "EUR" in details["document"]["content"]
    assert "Reverse" in details["document"]["content"] and "Lastmile" not in details["document"]["content"]
    agents = {r["agent"] for r in details["trace"]}
    assert {"human_approval_interrupt", "human_approval_resume", "record_decision", "arbitration", "final_document_synthesizer"} <= agents
    assert all(set(("agent", "input", "output", "timestamp")) <= set(r) for r in details["trace"])
    assert all("token" not in s for s in details["sections"])


def test_human_changes_revise_only_affected_branch_and_cap(ready):
    identifier, approvals = ready
    process_approval(approvals, identifier, "warehouse")
    process_approval(approvals, identifier, "reverse")
    approve(approvals, identifier, "reverse", "sofia")
    for _ in range(3):
        b = approvals.branch(identifier, "warehouse")
        approvals.respond(identifier, "warehouse", "ana", "request_changes", b.version, "Clarify the onboarding confirmation process.")
        process_approval(approvals, identifier, "warehouse", ProposalFixture())
        assert approvals.branch(identifier, "reverse").approved_version == 1
    b = approvals.branch(identifier, "warehouse")
    assert b.version == 4 and b.revision_count == 3 and b.approval_status == "pending"
    with pytest.raises(ApprovalError, match="limit"):
        approvals.respond(identifier, "warehouse", "ana", "request_changes", b.version, "Again")
    approve(approvals, identifier, "warehouse", "ana")
    assert approvals.details(identifier, "alice")["status"] == "done"


def test_identity_stale_version_rejection_and_duplicate_guard(ready):
    identifier, approvals = ready
    with pytest.raises(ApprovalError):
        approvals.respond(identifier, "warehouse", "sofia", "approve", 1)
    with pytest.raises(ApprovalError):
        approvals.respond(identifier, "warehouse", "ana", "approve", 99)
    approvals.respond(identifier, "warehouse", "ana", "reject", 1, "We cannot support this proposal.")
    with pytest.raises(ApprovalError):
        approvals.respond(identifier, "warehouse", "ana", "approve", 1)
    process_approval(approvals, identifier, "warehouse")
    approve(approvals, identifier, "reverse", "sofia")
    assert approvals.branch(identifier, "warehouse").approval_status == "rejected"
    assert approvals.details(identifier, "alice")["document"] is None


def test_arbitration_owner_and_currency_fix(ready):
    identifier, approvals = ready
    with Session(approvals.engine) as db:
        b = db.get(ApprovalBranch, (identifier, "warehouse"))
        b.draft = dict(b.draft, currency="USD", content=b.draft["content"].replace("EUR", "USD"))
        db.add(b)
        db.commit()
    process_approval(approvals, identifier, "warehouse")
    assert approvals.details(identifier, "miguel")["conflicts"][0]["trigger_id"] == "currency-mismatch"
    with pytest.raises(ApprovalError):
        approvals.respond(identifier, "warehouse", "ana", "approve", 1)
    with pytest.raises(ApprovalError):
        approvals.resolve(identifier, "ana", "currency-mismatch", "request_changes", "Use EUR")
    approvals.resolve(identifier, "miguel", "currency-mismatch", "request_changes", "Use EUR for Spain.")
    process_approval(approvals, identifier, "warehouse", ProposalFixture())
    assert approvals.branch(identifier, "warehouse").version == 2
    assert approvals.details(identifier, "alice")["conflicts"][0]["status"] == "resolved"
    approve(approvals, identifier, "warehouse", "ana")
    approve(approvals, identifier, "reverse", "sofia")
    assert approvals.details(identifier, "alice")["status"] == "done"


def test_three_structured_triggers_and_unit_safety():
    def branch(department, **changes):
        return ApprovalBranch(ticket_id="t", department_id=department, version=1, draft=dict(draft(department), **changes), evaluation={})
    cap = {"value": 100, "unit": "orders", "period": "month", "evidence": "Confirmed 100 orders per month"}
    volume = dict(cap, value=200)
    rows = [branch("warehouse", commitments={"capacity": cap}), branch("lastmile", commitments={"volume": volume}),
            branch("reverse", returns_turnaround_hours=24, currency="USD")]
    found = {f["trigger_id"]: f for f in conflicts(rows, "ES")}
    assert set(found) == {"volume-vs-capacity", "returns-sla-breach", "currency-mismatch"}
    assert found["returns-sla-breach"]["arbiter"] == "reverse"
    rows[1].draft = dict(rows[1].draft, commitments={"volume": dict(volume, unit="skus")})
    assert "volume-vs-capacity" not in {f["trigger_id"] for f in conflicts(rows, "ES")}


def test_durable_restart_and_ticket_namespace(tmp_path):
    path = tmp_path / "business.sqlite"
    engine = create_engine(f"sqlite:///{path}")
    create_tables(engine)
    identifier, approvals = prepared(Store(engine), tmp_path)
    process_approval(approvals, identifier, "warehouse")
    engine.dispose()
    engine = create_engine(f"sqlite:///{path}")
    approvals = ApprovalStore(engine)
    approve(approvals, identifier, "warehouse", "ana")
    assert approvals.branch(identifier, "warehouse").approval_status == "approved"
    with checkpoint_saver(engine) as saver:
        assert saver.get_tuple({"configurable": {"thread_id": "rfp-another-ticket:warehouse"}}) is None
    engine.dispose()


def test_provider_failure_keeps_decision_and_resumes_revision(ready):
    identifier, approvals = ready
    process_approval(approvals, identifier, "warehouse")
    approvals.respond(identifier, "warehouse", "ana", "request_changes", 1, "Clarify onboarding.")
    with pytest.raises(RuntimeError):
        process_approval(approvals, identifier, "warehouse", ProposalFixture(crash_once=True))
    assert approvals.branch(identifier, "warehouse").error
    process_approval(approvals, identifier, "warehouse", ProposalFixture())
    assert approvals.branch(identifier, "warehouse").version == 2
    assert approvals.branch(identifier, "warehouse").approval_status == "pending"


def test_capped_part2_sections_not_automatically_approved(store, tmp_path):
    t = ticket(store, tmp_path)
    process_ticket(store, t.ticket_id, ModelFixture(), lambda _: FORMAL)
    ProposalStore(store.engine).start(t.ticket_id, "alice")
    process_proposal(ProposalStore(store.engine), t.ticket_id, ProposalFixture(fail_until=100))
    approvals = ApprovalStore(store.engine)
    for d, user in [("warehouse", "ana"), ("reverse", "sofia")]:
        approvals.assign(t.ticket_id, "alice", d, user)
    approvals.start(t.ticket_id, "alice")
    with pytest.raises(ApprovalError):
        approvals.respond(t.ticket_id, "warehouse", "ana", "approve", 3)
    assert approvals.details(t.ticket_id, "alice")["document"] is None


def test_structured_quantities_require_actual_numeric_unit_period_evidence():
    from data.pipelines.rfp_intake.approval_rules import Quantity, quantity_grounded
    from pydantic import ValidationError
    quote = "Confirmed monthly capacity: 1,000 orders."
    quantity = Quantity(value=1000, unit="orders", period="month", evidence=quote)
    assert quantity_grounded(quantity, quote)
    assert not quantity_grounded(quantity.model_copy(update={"value": 2000}), quote)
    assert not quantity_grounded(quantity.model_copy(update={"unit": "skus"}), quote)
    assert not quantity_grounded(quantity.model_copy(update={"period": "day"}), quote)
    with pytest.raises(ValidationError):
        Quantity(value=float("inf"), unit="orders", period="month", evidence=quote)


def test_capacity_correction_cannot_hide_volume_or_preserve_higher_quoted_total():
    from data.pipelines.rfp_intake.approval_rules import capacity_revision_valid
    cap = {"value": 100, "unit": "orders", "period": "month", "evidence": "100 orders monthly"}
    cost = {"amount": 200, "currency": "EUR", "period": "month", "evidence": "200 EUR monthly"}
    previous = {"commitments": {"volume": dict(cap, value=200), "customer_total_cost": cost}}
    corrected = {"commitments": {"volume": cap, "customer_total_cost": dict(cost, amount=100)}}
    assert capacity_revision_valid(previous, corrected, cap)
    assert not capacity_revision_valid(previous, {"commitments": {"volume": cap}}, cap)
    assert not capacity_revision_valid(previous, {"commitments": {"volume": cap, "customer_total_cost": cost}}, cap)
    assert not capacity_revision_valid(previous, {"commitments": {}}, cap)
