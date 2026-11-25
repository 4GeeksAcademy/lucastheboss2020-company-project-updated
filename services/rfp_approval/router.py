"""Additive approval commands; reuse existing login and keep intake ACL unchanged."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, select
from backend.auth import get_current_user
from backend.services import get_user_by_id
from services.database import engine
from services.rfp_intake.router import owner
from services.rfp_intake.models import Ticket
from .models import Reviewer
from .store import ApprovalStore, ApprovalError

router = APIRouter(prefix="/rfp", tags=["RFP approvals"])


def get_store():
    return ApprovalStore(engine)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Assignment(Strict):
    department_id: str = Field(max_length=30)
    user_id: str = Field(min_length=1, max_length=100)


class Decision(Strict):
    decision: str = Field(max_length=30)
    version: int = Field(ge=1)
    feedback: str = Field(default="", max_length=5000)


class Arbitration(Strict):
    trigger_id: str = Field(max_length=50)
    decision: str = Field(max_length=30)
    feedback: str = Field(min_length=1, max_length=5000)


def call(fn, *args):
    try:
        return fn(*args)
    except ApprovalError as exc:
        raise HTTPException(exc.code, str(exc)) from None


def dispatch(store, ticket_id):
    from services.celery_app import app
    try:
        for b in store.branches(ticket_id):
            if b.approval_status not in {"approved", "rejected", "blocked"}:
                app.send_task("run_rfp_approval", args=[ticket_id, b.department_id], queue="reporting")
    except Exception:
        raise HTTPException(503, "Saved successfully, but processing could not be queued. Retry approval processing.") from None


@router.get("/approvals/inbox")
def inbox(user: dict = Depends(get_current_user), store: ApprovalStore = Depends(get_store)):
    with Session(store.engine) as db:
        rows = db.exec(select(Ticket).join(Reviewer, Reviewer.ticket_id == Ticket.ticket_id).where(Reviewer.user_id == owner(user))).all()
        return [{"ticket_id": t.ticket_id, "status": t.status} for t in {t.ticket_id: t for t in rows}.values()]


@router.get("/tickets/{ticket_id}/approvals")
def details(ticket_id: UUID, user: dict = Depends(get_current_user), store: ApprovalStore = Depends(get_store)):
    return call(store.details, str(ticket_id), owner(user))


@router.post("/tickets/{ticket_id}/approvals/reviewers")
def assign(ticket_id: UUID, body: Assignment, user: dict = Depends(get_current_user), store: ApprovalStore = Depends(get_store)):
    target = get_user_by_id(body.user_id)
    if not target or not target.get("is_active"):
        raise HTTPException(422, "Choose an existing active TrackFlow user ID.")
    call(store.assign, str(ticket_id), owner(user), body.department_id, body.user_id)
    return call(store.details, str(ticket_id), owner(user))


@router.post("/tickets/{ticket_id}/approvals", status_code=202)
def start(ticket_id: UUID, user: dict = Depends(get_current_user), store: ApprovalStore = Depends(get_store)):
    call(store.start, str(ticket_id), owner(user))
    dispatch(store, str(ticket_id))
    return call(store.details, str(ticket_id), owner(user))


@router.post("/tickets/{ticket_id}/approvals/retry", status_code=202)
def retry(ticket_id: UUID, user: dict = Depends(get_current_user), store: ApprovalStore = Depends(get_store)):
    data = call(store.details, str(ticket_id), owner(user))
    if not data["sections"]:
        raise HTTPException(409, "Start department approvals first.")
    # Recover finalization after a worker stopped immediately after the last sign-off.
    call(store.complete, str(ticket_id))
    dispatch(store, str(ticket_id))
    return call(store.details, str(ticket_id), owner(user))


@router.post("/tickets/{ticket_id}/approvals/{department}/resume", status_code=202)
def resume(ticket_id: UUID, department: str, body: Decision, user: dict = Depends(get_current_user), store: ApprovalStore = Depends(get_store)):
    call(store.respond, str(ticket_id), department, owner(user), body.decision, body.version, body.feedback)
    dispatch(store, str(ticket_id))
    return call(store.details, str(ticket_id), owner(user))


@router.post("/tickets/{ticket_id}/approvals/arbitrate", status_code=202)
def arbitrate(ticket_id: UUID, body: Arbitration, user: dict = Depends(get_current_user), store: ApprovalStore = Depends(get_store)):
    call(store.resolve, str(ticket_id), owner(user), body.trigger_id, body.decision, body.feedback)
    dispatch(store, str(ticket_id))
    return call(store.details, str(ticket_id), owner(user))


@router.get("/tickets/{ticket_id}/approvals/document")
def document(ticket_id: UUID, user: dict = Depends(get_current_user), store: ApprovalStore = Depends(get_store)):
    result = call(store.details, str(ticket_id), owner(user))
    if result["status"] != "done" or not result["document"]:
        raise HTTPException(409, "The final approved document is not available yet.")
    return Response(result["document"]["content"], media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="trackflow-{ticket_id}.md"'})
