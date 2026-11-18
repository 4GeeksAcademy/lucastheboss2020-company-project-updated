"""Background execution boundary. The graph itself stays in data/pipelines/."""

from pathlib import Path
import asyncio
from .ingestion import convert_pdf, DocumentError
from .graph import create_graph


def process_ticket(store, ticket_id, model=None, converter=None):
    claim = store.claim(ticket_id)
    if claim is None:
        return {"ticket_id": ticket_id, "status": "not_claimed"}
    ticket, token = claim
    try:
        store.progress(ticket_id, token, "Converting PDF to Markdown")
        text = (converter or convert_pdf)(Path(ticket.raw_pdf_path))
        # Sidecar is disposable; PostgreSQL is the authoritative business record.
        Path(ticket.raw_pdf_path).with_suffix(".md").write_text(text, encoding="utf-8")
        graph = create_graph(model, lambda stage: store.progress(ticket_id, token, stage))
        state = asyncio.run(graph.ainvoke({"markdown": text, "sections": []}, {"recursion_limit": 10}))
        committed = store.finish(ticket_id, token, state)
        return {
            "ticket_id": ticket_id,
            "status": ("intake_complete" if state["classification"]["accepted"] else "discarded")
            if committed
            else "superseded",
        }
    except DocumentError as exc:
        store.fail(ticket_id, token, "document_unreadable", str(exc))
        return {"ticket_id": ticket_id, "status": "processing_failed"}
    except Exception:
        store.fail(
            ticket_id, token, "analysis_failed", "Analysis could not be completed. Retry or contact the TrackFlow team."
        )
        raise RuntimeError("RFP analysis failed; see sanitized ticket error.") from None
