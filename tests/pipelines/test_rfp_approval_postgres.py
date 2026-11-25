"""Real PostgreSQL checkpoints and concurrent decisions, using a disposable test DB."""
from concurrent.futures import ThreadPoolExecutor
from tests.pipelines.test_rfp_postgres import pgstore as pgstore
from tests.pipelines.test_rfp_approval import prepared, approve
from services.rfp_approval.store import ApprovalStore, ApprovalError
from data.pipelines.rfp_intake.approval_graph import process_approval


def test_postgres_independent_pauses_fresh_store_resume_and_final(pgstore, tmp_path):
    identifier, approvals = prepared(pgstore, tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda d: process_approval(approvals, identifier, d), ["warehouse", "reverse"]))
    approvals = ApprovalStore(pgstore.engine)
    approve(approvals, identifier, "reverse", "sofia")
    assert approvals.branch(identifier, "warehouse").approval_status == "pending"
    assert approvals.details(identifier, "alice")["document"] is None
    approve(approvals, identifier, "warehouse", "ana")
    assert ApprovalStore(pgstore.engine).details(identifier, "alice")["status"] == "done"


def test_postgres_concurrent_human_response_has_one_winner(pgstore, tmp_path):
    identifier, approvals = prepared(pgstore, tmp_path)
    process_approval(approvals, identifier, "warehouse")
    def submit(_):
        try:
            approvals.respond(identifier, "warehouse", "ana", "approve", 1)
            return "accepted"
        except ApprovalError:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(submit, range(2))).count("accepted") == 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(lambda _: process_approval(approvals, identifier, "warehouse"), range(2)))
    assert sum(r["status"] == "complete" for r in result) == 1
    assert approvals.branch(identifier, "warehouse").approval_status == "approved"
