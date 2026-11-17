"""Offline tests use explicit model fixtures; production never falls back to these."""

import asyncio, copy
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine, Session, select
from data.pipelines.rfp_intake.graph import create_graph, AgentOutputError
from data.pipelines.rfp_intake.ingestion import convert_pdf, readability, DocumentError
from data.pipelines.rfp_intake.runner import process_ticket
from services.rfp_intake.models import Ticket, DepartmentSection, create_tables, now
from services.rfp_intake.store import Store

FORMAL = "ModaViva in Spain requests warehousing and returns. We use our own carrier for delivery."
INFORMAL = "Luna Cosmetics in Los Angeles requests warehousing and last-mile delivery for about 5,000 orders/month."
INVALID = "We are a carrier offering our discounted rate card to TrackFlow. Please buy our delivery services."


class ModelFixture:
    def __init__(self, text=FORMAL, mutate=None):
        self.text = text
        self.calls = []
        self.mutate = mutate

    def generate(self, role, payload, schema):
        self.calls.append((role, payload))
        if role.startswith("classifier"):
            result = {
                "accepted": self.text != INVALID,
                "reason": "Client requests logistics services."
                if self.text != INVALID
                else "Supplier offers services to TrackFlow.",
                "evidence": [self.text],
            }
        elif role.startswith("orchestrator"):
            depts = ["warehouse", "reverse"] if self.text == FORMAL else ["warehouse", "lastmile"]
            metadata = {
                "client_name": "ModaViva" if self.text == FORMAL else "Luna Cosmetics",
                "client_country": "ES" if self.text == FORMAL else "US",
                "services_requested": depts,
                "monthly_volume": None if self.text == FORMAL else "about 5,000 orders/month",
                "deadline": None,
                "budget_range": None,
                "evidence": {},
            }
            metadata["evidence"] = {k: [self.text] for k, v in metadata.items() if v is not None and k != "evidence"}
            result = {
                "metadata": metadata,
                "assignments": [{"department_id": d, "extracts": [self.text]} for d in depts],
                "open_questions": ["What is the proposal deadline?"],
            }
        elif role.startswith("department worker"):
            result = {
                "department_id": payload["department_id"],
                "key_aspects": [{"requirement": "Review requested logistics services.", "evidence": self.text}],
                "open_questions": ["What onboarding date is required?"],
            }
        else:
            result = {
                "summary": "Sales should ask the selected department owners to review the customer requirements.",
                "open_questions": ["What is the proposal deadline?"],
                "conflicts": [],
            }
        return self.mutate(schema, result, payload) if self.mutate else result


@pytest.fixture
def store(tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    create_tables(engine)
    yield Store(engine)
    engine.dispose()


def ticket(store, tmp_path, owner="alice"):
    path = tmp_path / (str(uuid4()) + ".pdf")
    path.write_bytes(b"%PDF-fixture")
    return store.create(
        Ticket(owner_id=owner, original_filename="request.pdf", raw_pdf_path=str(path), sha256="a" * 64)
    )


@pytest.mark.parametrize(
    "text,depts,currency", [(FORMAL, {"warehouse", "reverse"}, "EUR"), (INFORMAL, {"warehouse", "lastmile"}, "USD")]
)
def test_valid_graph(text, depts, currency):
    model = ModelFixture(text)
    state = asyncio.run(create_graph(model).ainvoke({"markdown": text, "sections": []}))
    result = state["result"]
    assert {s["department_id"] for s in result["sections"]} == depts
    assert result["metadata"]["currency"] == currency
    assert result["ready_for_part2"] and result["next_step"] == "proposal_generation"
    workers = [p for role, p in model.calls if role.startswith("department worker")]
    assert len(workers) == 2 and all(set(p) == {"department_id", "metadata", "source_excerpts"} for p in workers)
    assert all("markdown" not in p for p in workers)
    assert result["metadata"]["monthly_volume"] == (None if text == FORMAL else "about 5,000 orders/month")
    assert all(s["owner"] for s in result["sections"])


def test_rejected_stops_workers():
    model = ModelFixture(INVALID)
    state = asyncio.run(create_graph(model).ainvoke({"markdown": INVALID, "sections": []}))
    assert not state["classification"]["accepted"] and "result" not in state and len(model.calls) == 1


@pytest.mark.parametrize(
    "kind",
    [
        "fabricated_quote",
        "fabricated_volume",
        "duplicate_department",
        "unknown_department",
        "wrong_worker",
        "worker_number",
        "synthesis_number",
        "extra_field",
    ],
)
def test_invalid_model_outputs_fail_closed(kind):
    def mutate(schema, r, p):
        r = copy.deepcopy(r)
        if kind == "fabricated_quote" and schema.__name__ == "Classification":
            r["evidence"] = ["This was never in the document."]
        if schema.__name__ == "Plan":
            if kind == "fabricated_volume":
                r["metadata"]["monthly_volume"] = "10,000 orders"
            if kind == "duplicate_department":
                r["assignments"].append(r["assignments"][0])
            if kind == "unknown_department":
                r["assignments"][0]["department_id"] = "finance"
        if schema.__name__ == "WorkerResult":
            if kind == "wrong_worker":
                r["department_id"] = "lastmile"
            if kind == "worker_number":
                r["key_aspects"][0]["requirement"] = "TrackFlow supports 999999 pallets."
        if kind == "synthesis_number" and schema.__name__ == "Synthesis":
            r["summary"] = "TrackFlow guarantees 999999 shipments."
        if kind == "extra_field":
            r["system_override"] = "ignore policy"
        return r

    with pytest.raises((ValueError, AgentOutputError)):
        asyncio.run(create_graph(ModelFixture(mutate=mutate)).ainvoke({"markdown": FORMAL, "sections": []}))


def test_persist_complete_and_idempotent(store, tmp_path):
    t = ticket(store, tmp_path)
    r = process_ticket(store, t.ticket_id, ModelFixture(), lambda p: FORMAL)
    assert r["status"] == "intake_complete"
    result = store.details(t.ticket_id, "alice")
    assert result["handoff"]["ticket_id"] == t.ticket_id
    assert len(result["sections"]) == 2 and result["metadata"]["currency"] == "EUR"
    assert not result["can_retry"] and not store.details(t.ticket_id, "bob")
    assert not any(k in result for k in ["owner_id", "raw_pdf_path", "run_token", "sha256", "lease_until"])
    assert process_ticket(store, t.ticket_id, ModelFixture(), lambda p: FORMAL)["status"] == "not_claimed"
    with Session(store.engine) as db:
        assert len(db.exec(select(DepartmentSection)).all()) == 2


def test_rejected_persist_metrics_no_sections(store, tmp_path):
    t = ticket(store, tmp_path)
    process_ticket(store, t.ticket_id, ModelFixture(INVALID), lambda p: INVALID)
    d = store.details(t.ticket_id, "alice")
    assert d["status"] == "discarded" and not d["sections"] and d["handoff"] is None
    assert d["metadata"]["readability_metrics"]["word_count"] > 0 and not d["can_retry"]


def test_document_failure_not_discarded_and_does_not_call_model(store, tmp_path):
    t = ticket(store, tmp_path)
    m = ModelFixture()

    def broken(p):
        raise DocumentError("No usable text was found.")

    process_ticket(store, t.ticket_id, m, broken)
    d = store.details(t.ticket_id, "alice")
    assert d["status"] == "analyzing" and d["processing_state"] == "failed" and d["can_retry"]
    assert not m.calls and not d["sections"]


def test_failed_job_no_partial_success_and_retry(store, tmp_path):
    t = ticket(store, tmp_path)
    m = ModelFixture(mutate=lambda schema, r, p: {"broken": True} if schema.__name__ == "Synthesis" else r)
    with pytest.raises(RuntimeError):
        process_ticket(store, t.ticket_id, m, lambda p: FORMAL)
    assert not store.details(t.ticket_id, "alice")["sections"]
    assert store.prepare_retry(t.ticket_id, "alice")
    process_ticket(store, t.ticket_id, ModelFixture(), lambda p: FORMAL)
    assert store.details(t.ticket_id, "alice")["status"] == "intake_complete"


def test_claim_exclusion_and_stale_result(store, tmp_path):
    t = ticket(store, tmp_path)
    claim = store.claim(t.ticket_id)
    assert claim and store.claim(t.ticket_id) is None
    store.progress(t.ticket_id, "wrong", "Fake success")
    assert store.details(t.ticket_id, "alice")["stage"] != "Fake success"
    store.fail(t.ticket_id, None, "queue", "queue failed")
    assert store.details(t.ticket_id, "alice")["processing_state"] == "running"
    with Session(store.engine) as db:
        row = db.get(Ticket, t.ticket_id)
        row.updated_at = now() - timedelta(minutes=20)
        db.add(row)
        db.commit()
    assert store.details(t.ticket_id, "alice")["stalled"]
    assert not store.prepare_retry(t.ticket_id, "bob") and store.prepare_retry(t.ticket_id, "alice")
    assert store.finish(t.ticket_id, claim[1], {}) is False


def test_retry_cap(store, tmp_path):
    t = ticket(store, tmp_path)
    with Session(store.engine) as db:
        row = db.get(Ticket, t.ticket_id)
        row.attempts = 6
        row.processing_state = "failed"
        db.add(row)
        db.commit()
    assert not store.prepare_retry(t.ticket_id, "alice") and not store.details(t.ticket_id, "alice")["can_retry"]


def test_tickets_isolated_when_one_fails(store, tmp_path):
    bad = ticket(store, tmp_path)
    good = ticket(store, tmp_path)
    process_ticket(store, bad.ticket_id, ModelFixture(INVALID), lambda p: INVALID)
    process_ticket(store, good.ticket_id, ModelFixture(), lambda p: FORMAL)
    assert store.details(good.ticket_id, "alice")["status"] == "intake_complete"
    assert store.details(bad.ticket_id, "alice")["status"] == "discarded"


def test_metrics_short_and_large_text():
    short = readability(FORMAL)
    assert short["availability"] == "insufficient_text" and short["flesch_kincaid"] is None
    long = readability(("The customer requests storage and delivery services for its products. " * 25))
    assert long["word_count"] >= 100 and long["estimated_tokens"] > 0


def test_conversion_bad_pdf(tmp_path):
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"%PDF-corrupt")
    with pytest.raises(DocumentError):
        convert_pdf(p)


def test_conversion_real_pdf_before_agents(tmp_path):
    from pypdf import PdfWriter

    p = tmp_path / "blank.pdf"
    w = PdfWriter()
    w.add_blank_page(width=500, height=500)
    w.write(p)
    with pytest.raises(DocumentError, match="No usable text"):
        convert_pdf(p)


def test_source_ids_resolve_to_exact_document_text():
    from data.pipelines.rfp_intake.graph import resolve_quotes, evidence_checked, source_catalog

    source = "First source paragraph.\n\nSecond source paragraph."
    assert resolve_quotes(["S0002"], source) == ["Second source paragraph."]
    assert len(source_catalog(source)) == 2
    with pytest.raises(AgentOutputError):
        evidence_checked(resolve_quotes(["S9999"], source), source)
