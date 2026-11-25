"""Additive proposal commands; normal TrackFlow authentication and ownership apply."""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from backend.auth import get_current_user
from services.database import engine
from services.rfp_intake.router import owner
from services.rfp_intake.store import Store
from .store import ProposalStore

router = APIRouter(prefix="/rfp", tags=["RFP proposals"])
logger = logging.getLogger(__name__)


def get_store():
    return ProposalStore(engine)


def dispatch(ticket_id):
    from services.celery_app import app

    app.send_task("run_rfp_proposal", args=[ticket_id], queue="reporting")


def schedule(ticket_id, actor, store, retry=False):
    result = store.start(ticket_id, actor, retry)
    if result == "not_found":
        raise HTTPException(404, "Ticket not found.")
    if result != "accepted":
        raise HTTPException(
            409,
            "Proposal generation requires a completed intake handoff; only interrupted runs below the retry limit can resume.",
        )
    try:
        dispatch(ticket_id)
    except Exception:
        store.fail(ticket_id)
        logger.warning("Proposal enqueue unavailable ticket_id=%s", ticket_id)
    return Store(store.engine).details(ticket_id, actor)


@router.post("/tickets/{ticket_id}/proposal", status_code=202)
def generate(ticket_id: UUID, user: dict = Depends(get_current_user), store: ProposalStore = Depends(get_store)):
    return schedule(str(ticket_id), owner(user), store)


@router.post("/tickets/{ticket_id}/proposal/retry", status_code=202)
def retry(ticket_id: UUID, user: dict = Depends(get_current_user), store: ProposalStore = Depends(get_store)):
    return schedule(str(ticket_id), owner(user), store, retry=True)
