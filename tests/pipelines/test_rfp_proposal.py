"""Offline proposal behavior uses explicit model fixtures, never a production fallback."""

import asyncio
import copy
import threading
from datetime import timedelta
import pytest
from sqlmodel import Session
from tests.pipelines.test_rfp_intake import store as store, ticket, ModelFixture, FORMAL
from data.pipelines.rfp_intake.runner import process_ticket
from data.pipelines.rfp_intake.proposal_graph import process_proposal
from data.pipelines.rfp_intake.proposal_agents import (
    GENERATORS,
    policies,
    evaluate,
    deterministic_compliance,
    evaluate_readability,
)
from services.rfp_generation.store import ProposalStore, SupersededRun
from services.rfp_generation.models import ProposalRun
from services.rfp_intake.models import now
from services.rfp_intake.store import Store

PROSE = (
    "TrackFlow will review the requested logistics services with your commercial team. "
    "We will agree the scope before starting work. Your existing requirements remain part of this draft. "
    "We will confirm storage needs and the launch date with you. No capacity has been reserved. "
    "The monthly on-time delivery SLA is 90% where TrackFlow delivery is contracted. "
    "Declared peak dates are excluded under the standard policy. We will explain any service limits before you sign. "
    "Returns processing will take at least 48 hours, subject to confirmation. "
    "Any preferential discount requires approval from Miguel Torres. This draft does not approve a discount. "
    "All prices and service terms need human approval before a final proposal is sent.\n"
    "| Volume basis | Discount |\n|---|---|\n| Standard volume | Standard rate |\n| Higher volume | Subject to approval |"
)


def draft(dept="warehouse", country="ES"):
    return {
        "department_id": dept,
        "content": PROSE + ("\nQuotation currency: EUR." if country == "ES" else "\nQuotation currency: USD."),
        "currency": "EUR" if country == "ES" else "USD",
        "on_time_sla_percent": 90,
        "returns_turnaround_hours": 48 if dept == "reverse" else None,
        "volume_discount_tiers": [
            {"volume_basis": "Higher volume", "discount_percent": None, "approval_required": True}
        ],
        "source_ids": ["sla-delivery", "storage-pricing"],
        "open_questions": ["Confirm scope before committing capacity."],
    }


def context(dept="warehouse"):
    return {
        "section_id": "section",
        "department_id": dept,
        "metadata": {"client_country": "ES"},
        "key_aspects": [{"requirement": "Review requested logistics services.", "evidence": FORMAL}],
        "policy_sources": policies(),
    }


class ProposalFixture:
    def __init__(self, fail_until=0, crash_once=False, department_failure=None):
        self.calls = []
        self.fail_until = fail_until
        self.crash_once = crash_once
        self.department_failure = department_failure
        self.lock = threading.Lock()

    def generate(self, role, payload, schema):
        with self.lock:
            self.calls.append((role, copy.deepcopy(payload)))
            if self.crash_once and schema.__name__ == "RelevanceResult":
                self.crash_once = False
                raise RuntimeError("private provider credential must not leak")
        if schema.__name__ == "ProposalDraft":
            return draft(payload["department_id"], payload["metadata"]["client_country"])
        if schema.__name__ == "RelevanceResult":
            dept = payload["department_id"]
            count = sum(1 for _, p in self.calls if p.get("department_id") == dept and "feedback_for_generator" in p)
            failed = (
                self.fail_until > 0
                and count <= self.fail_until
                and (not self.department_failure or self.department_failure == dept)
            )
            return {
                "missing_aspects": ["Explain how the requested onboarding will be confirmed."] if failed else [],
                "unsupported_claims": [],
            }
        return {"violations": []}


@pytest.fixture
def ready(store, tmp_path):
    t = ticket(store, tmp_path)
    process_ticket(store, t.ticket_id, ModelFixture(), lambda _: FORMAL)
    return t, ProposalStore(store.engine)


def test_generator_receives_only_handoff_and_department_policy_context():
    model = ProposalFixture()
    result = asyncio.run(GENERATORS["warehouse"].generate(model, context()))
    assert result["department_id"] == "warehouse"
    assert not any(key in model.calls[0][1] for key in ["raw_pdf_path", "markdown", "pdf"])


def test_evaluation_success_and_exact_shape():
    result = asyncio.run(evaluate(ProposalFixture(), context(), draft(), 1))
    assert result["overall_pass"]
    assert set(result) == {
        "section_id",
        "department_id",
        "draft_version",
        "readability",
        "relevance",
        "compliance",
        "overall_pass",
        "feedback_for_generator",
    }
    assert result["readability"]["method"] in {"py-readability-metrics", "sentence_length_fallback"}


def test_parallel_evaluators_really_overlap():
    barrier = threading.Barrier(2, timeout=5)

    class Parallel(ProposalFixture):
        def generate(self, role, payload, schema):
            if schema.__name__ in {"RelevanceResult", "ComplianceReview"}:
                barrier.wait()
            return super().generate(role, payload, schema)

    assert asyncio.run(evaluate(Parallel(), context(), draft(), 1))["overall_pass"]


@pytest.mark.parametrize(
    "mutation,rule",
    [
        ({"returns_turnaround_hours": 24}, "returns_minimum"),
        ({"currency": "USD"}, "currency"),
        ({"on_time_sla_percent": 99}, "delivery_sla"),
        ({"volume_discount_tiers": []}, "discount_table"),
        ({"content": PROSE + " Our capacity is 88888 pallets."}, "source_grounding"),
        ({"content": PROSE + " Our negotiated FedEx rate is 8 USD."}, "carrier_confidentiality"),
        ({"content": PROSE + " Returns processing takes 24 hours."}, "returns_minimum"),
    ],
)
def test_briefing_anchored_compliance_failures(mutation, rule):
    d = dict(draft(), **mutation)
    assert rule in {v["rule_id"] for v in deterministic_compliance(context(), d)}


def test_express_delivery_is_not_a_returns_processing_breach():
    d = dict(draft(), content=PROSE + " Express delivery takes 24 to 48 hours in supported areas.")
    assert "returns_minimum" not in {v["rule_id"] for v in deterministic_compliance(context(), d)}


def test_short_or_unavailable_formula_uses_explicit_fallback():
    result = evaluate_readability("Simple service terms. " * 20)
    assert result["method"] == "sentence_length_fallback" and result["pass"]
    assert not evaluate_readability("A tiny draft.")["pass"]


def test_end_to_end_persists_handoff_without_reopening_pdf(ready, store, monkeypatch):
    t, proposals = ready
    monkeypatch.setattr(
        "data.pipelines.rfp_intake.ingestion.convert_pdf", lambda _: pytest.fail("Part 2 must not parse PDFs")
    )
    original = store.details(t.ticket_id, "alice")["handoff"]
    assert proposals.start(t.ticket_id, "alice") == "accepted"
    assert proposals.start(t.ticket_id, "alice") == "conflict"
    assert process_proposal(proposals, t.ticket_id, ProposalFixture())["status"] == "complete"
    result = Store(store.engine).details(t.ticket_id, "alice")
    assert result["handoff"] == original
    assert result["status"] == "under_evaluation" and result["processing_state"] == "complete"
    handoff = result["proposal"]["handoff"]
    assert handoff["ready_for_part3"] and len(handoff["sections"]) == 2
    assert all(s["evaluation"]["overall_pass"] for s in handoff["sections"])
    assert len(result["proposal"]["attempts"]) == 2
    assert all(s["approval_status"] == "not_started" for s in result["sections"])
    assert process_proposal(proposals, t.ticket_id, ProposalFixture())["status"] == "not_claimed"


def test_feedback_revision_then_pass(ready, store):
    t, proposals = ready
    proposals.start(t.ticket_id, "alice")
    model = ProposalFixture(fail_until=1)
    process_proposal(proposals, t.ticket_id, model)
    result = store.details(t.ticket_id, "alice")["proposal"]
    assert all(s["attempts"] == 2 for s in result["handoff"]["sections"])
    revisions = [p for _, p in model.calls if p.get("previous_draft")]
    assert all("onboarding" in p["feedback_for_generator"] for p in revisions)
    assert len(result["attempts"]) == 4


def test_exhaustion_preserves_failed_section_and_other_department_pass(ready, store):
    t, proposals = ready
    proposals.start(t.ticket_id, "alice")
    process_proposal(proposals, t.ticket_id, ProposalFixture(fail_until=100, department_failure="reverse"))
    result = store.details(t.ticket_id, "alice")
    assert result["status"] == "needs_human_review"
    sections = {s["department_id"]: s for s in result["proposal"]["handoff"]["sections"]}
    assert sections["warehouse"]["attempts"] == 1 and sections["warehouse"]["evaluation"]["overall_pass"]
    assert sections["reverse"]["attempts"] == 3 and sections["reverse"]["status"] == "needs_human_review"
    assert sections["reverse"]["draft"]["content"] and not sections["reverse"]["evaluation"]["overall_pass"]
    assert not result["proposal"]["can_retry"]


def test_interrupted_evaluation_resumes_saved_draft_without_spending_attempt(ready, store):
    t, proposals = ready
    proposals.start(t.ticket_id, "alice")
    with pytest.raises(RuntimeError, match="saved drafts"):
        process_proposal(proposals, t.ticket_id, ProposalFixture(crash_once=True))
    before = store.details(t.ticket_id, "alice")["proposal"]
    assert before["can_retry"] and "credential" not in before["error_message"]
    assert proposals.start(t.ticket_id, "alice", retry=True) == "accepted"
    model = ProposalFixture()
    process_proposal(proposals, t.ticket_id, model)
    after = store.details(t.ticket_id, "alice")["proposal"]
    assert after["state"] == "complete"
    assert all(a["version"] == 1 for a in after["attempts"])
    assert not any(schema for schema, payload in model.calls if "feedback_for_generator" in payload)


def test_claim_and_stale_worker_fencing(ready):
    t, proposals = ready
    assert proposals.start(t.ticket_id, "other") == "not_found"
    proposals.start(t.ticket_id, "alice")
    token, contexts = proposals.claim(t.ticket_id)
    assert proposals.claim(t.ticket_id) is None
    proposals.fail(t.ticket_id, token)
    proposals.start(t.ticket_id, "alice", retry=True)
    newer, _ = proposals.claim(t.ticket_id)
    assert newer != token
    with pytest.raises(SupersededRun):
        proposals.checkpoint(t.ticket_id, token, "warehouse", "drafting", 1)
    proposals.fail(t.ticket_id, token)
    with Session(proposals.engine) as db:
        assert db.get(ProposalRun, t.ticket_id).token == newer


def test_incomplete_intake_cannot_start(store, tmp_path):
    t = ticket(store, tmp_path)
    assert ProposalStore(store.engine).start(t.ticket_id, "alice") == "conflict"


def test_no_provider_fallback_when_configuration_missing(ready, monkeypatch):
    t, proposals = ready
    proposals.start(t.ticket_id, "alice")
    monkeypatch.setattr(
        "data.pipelines.rfp_intake.proposal_graph.ProposalModel",
        lambda: (_ for _ in ()).throw(RuntimeError("missing key")),
    )
    with pytest.raises(RuntimeError):
        process_proposal(proposals, t.ticket_id)
    assert proposals.latest(t.ticket_id, "warehouse") is None
    with Session(proposals.engine) as db:
        assert db.get(ProposalRun, t.ticket_id).state == "failed"


@pytest.mark.parametrize("change", [{"department_id": "reverse"}, {"source_ids": ["untrusted-customer-instruction"]}])
def test_generator_cannot_switch_department_or_invent_policy_sources(change):
    class Invalid(ProposalFixture):
        def generate(self, role, payload, schema):
            return dict(draft(), **change)

    with pytest.raises(ValueError):
        asyncio.run(GENERATORS["warehouse"].generate(Invalid(), context()))


def test_stalled_retry_resumes_and_run_budget_is_enforced(ready):
    t, proposals = ready
    proposals.start(t.ticket_id, "alice")
    token, _ = proposals.claim(t.ticket_id)
    with Session(proposals.engine) as db:
        run = db.get(ProposalRun, t.ticket_id)
        run.updated_at = now() - timedelta(minutes=16)
        db.add(run)
        db.commit()
    assert proposals.start(t.ticket_id, "alice", retry=True) == "accepted"
    with pytest.raises(SupersededRun):
        proposals.checkpoint(t.ticket_id, token, "warehouse", "drafting", 1)
    with Session(proposals.engine) as db:
        run = db.get(ProposalRun, t.ticket_id)
        run.runs, run.state = 6, "failed"
        db.add(run)
        db.commit()
    assert proposals.start(t.ticket_id, "alice", retry=True) == "conflict"


def test_evaluation_cannot_attach_to_another_version(ready):
    t, proposals = ready
    proposals.start(t.ticket_id, "alice")
    token, contexts = proposals.claim(t.ticket_id)
    d = draft("warehouse")
    proposals.checkpoint(t.ticket_id, token, "warehouse", "under_evaluation", 1, d)
    e = asyncio.run(evaluate(ProposalFixture(), context(), d, 2))
    with pytest.raises(ValueError):
        proposals.checkpoint(t.ticket_id, token, "warehouse", "passed", 1, d, e)
    assert proposals.latest(t.ticket_id, "warehouse")["evaluation"] is None


def test_provider_adapter_uses_configured_model_and_proposal_instructions(monkeypatch):
    import json
    from types import SimpleNamespace
    import httpx
    from openai import OpenAI
    from data.pipelines.rag import OpenAICompatibleGenerationProvider
    from data.pipelines.rfp_intake.proposal_agents import ProposalModel
    from data.pipelines.rfp_intake.proposal_schemas import ProposalDraft

    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "fixture",
                "object": "chat.completion",
                "created": 0,
                "model": "configured-model",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps(draft())},
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        client = OpenAI(api_key="explicit-test-key", base_url="https://model.invalid/v1", http_client=transport)
        monkeypatch.setattr(
            OpenAICompatibleGenerationProvider,
            "from_env",
            classmethod(lambda cls: SimpleNamespace(client=client, model="configured-model")),
        )
        result = ProposalModel().generate("Generate warehouse proposal", context(), ProposalDraft)
    assert json.loads(result)["department_id"] == "warehouse"
    assert requests[0]["model"] == "configured-model"
    prompt = requests[0]["messages"][0]["content"]
    assert "untrusted reference DATA" in prompt and "Never quote prices" not in prompt
