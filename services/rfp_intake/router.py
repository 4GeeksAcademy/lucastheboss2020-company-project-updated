"""Authenticated RFP upload/status routes on the existing TrackFlow backend."""

from pathlib import Path
from uuid import UUID, uuid4
import hashlib, logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from services.database import engine
from backend.auth import get_current_user
from data.pipelines.rfp_intake.ingestion import MAX_BYTES
from .models import Ticket
from .store import Store

router = APIRouter(prefix="/rfp", tags=["RFP intake"])
logger = logging.getLogger(__name__)
RAW_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw" / "rfp"


def get_store():
    return Store(engine)


def owner(user):
    value = user.get("user_uuid") or user.get("id")
    if not value:
        raise HTTPException(403, "A verified TrackFlow account is required.")
    return str(value)


def dispatch(ticket_id):
    from services.celery_app import app

    app.send_task("run_rfp_intake", args=[ticket_id], queue="reporting")


def enqueue(store, ticket_id):
    try:
        dispatch(ticket_id)
    except Exception:
        store.fail(
            ticket_id,
            None,
            "queue_unavailable",
            "The upload was saved, but processing could not be queued. Retry this ticket.",
        )
        logger.warning("RFP enqueue unavailable ticket_id=%s", ticket_id)


@router.post("/tickets", status_code=202)
async def upload(
    file: UploadFile = File(...), user: dict = Depends(get_current_user), store: Store = Depends(get_store)
):
    actor = owner(user)
    if not (file.filename or "").lower().endswith(".pdf") or file.content_type not in {
        "application/pdf",
        "application/octet-stream",
    }:
        raise HTTPException(415, "Upload a PDF document.")
    content = await file.read(MAX_BYTES + 1)
    await file.close()
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "PDF must be no larger than 10 MB.")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(415, "The file does not have a valid PDF signature.")
    ticket_id = str(uuid4())
    folder = RAW_ROOT / ticket_id
    folder.mkdir(parents=True, exist_ok=False)
    path = folder / "request.pdf"
    path.write_bytes(content)
    name = Path((file.filename or "request.pdf").replace("\\", "/")).name
    name = "".join(c for c in name if c.isprintable())[:180] or "request.pdf"
    try:
        store.create(
            Ticket(
                ticket_id=ticket_id,
                owner_id=actor,
                original_filename=name,
                raw_pdf_path=str(path),
                sha256=hashlib.sha256(content).hexdigest(),
            )
        )
    except Exception:
        # This exact newly-created upload has no database record; do not leave an orphan.
        path.unlink(missing_ok=True)
        folder.rmdir()
        raise HTTPException(503, "The ticket could not be saved. Please retry the upload.") from None
    enqueue(store, ticket_id)
    return store.details(ticket_id, actor)


@router.get("/tickets")
def list_tickets(
    offset: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=50),
    user: dict = Depends(get_current_user),
    store: Store = Depends(get_store),
):
    return {"items": store.list(owner(user), offset, limit), "offset": offset, "limit": limit}


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: UUID, user: dict = Depends(get_current_user), store: Store = Depends(get_store)):
    result = store.details(str(ticket_id), owner(user))
    if not result:
        raise HTTPException(404, "Ticket not found.")
    return result


@router.post("/tickets/{ticket_id}/retry", status_code=202)
def retry_ticket(ticket_id: UUID, user: dict = Depends(get_current_user), store: Store = Depends(get_store)):
    actor = owner(user)
    identifier = str(ticket_id)
    if not store.owned(identifier, actor):
        raise HTTPException(404, "Ticket not found.")
    if not store.prepare_retry(identifier, actor):
        raise HTTPException(409, "Only failed or stalled intake tickets below the retry limit can be retried.")
    enqueue(store, identifier)
    return store.details(identifier, actor)
