from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from tests.pipelines.test_rfp_postgres import pgstore as pgstore
from tests.pipelines.test_rfp_intake import ticket, ModelFixture, FORMAL
from tests.pipelines.test_rfp_proposal import ProposalFixture
from data.pipelines.rfp_intake.runner import process_ticket
from data.pipelines.rfp_intake.proposal_graph import process_proposal
from services.rfp_generation.store import ProposalStore
from services.rfp_intake.store import Store


def seed(pgstore, tmp_path):
    t = ticket(pgstore, tmp_path, owner="proposal-test-" + str(uuid4()))
    process_ticket(pgstore, t.ticket_id, ModelFixture(), lambda _: FORMAL)
    return t, ProposalStore(pgstore.engine)


def test_postgres_proposal_roundtrip_and_version_history(pgstore, tmp_path):
    t, proposals = seed(pgstore, tmp_path)
    assert proposals.start(t.ticket_id, t.owner_id) == "accepted"
    process_proposal(proposals, t.ticket_id, ProposalFixture(fail_until=1))
    data = Store(pgstore.engine).details(t.ticket_id, t.owner_id)
    assert data["proposal"]["handoff"]["ready_for_part3"]
    assert len(data["proposal"]["attempts"]) == 4
    assert all(s["evaluation_results"]["overall_pass"] for s in data["sections"])


def test_postgres_duplicate_start_and_claim_have_one_winner(pgstore, tmp_path):
    t, proposals = seed(pgstore, tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        starts = list(pool.map(lambda _: proposals.start(t.ticket_id, t.owner_id), range(2)))
    assert starts.count("accepted") == 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: proposals.claim(t.ticket_id), range(2)))
    assert sum(value is not None for value in claims) == 1
