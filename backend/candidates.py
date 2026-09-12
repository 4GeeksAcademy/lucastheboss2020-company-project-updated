from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from tinydb import Query
from .auth import get_current_user
from .models import CandidatePatch, CandidateWrite, NoteCreate
from .storage import candidates_table

router = APIRouter(prefix="/candidates", tags=["candidates"])


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_candidate(candidate_id: str) -> dict | None:
    return candidates_table.get(Query().id == candidate_id)


@router.post("", status_code=201)
def create_candidate(payload: CandidateWrite):
    candidate = {"id": f"lead-{uuid4()}", **payload.model_dump(), "createdAt": now(), "updatedAt": now(), "notes": []}
    candidates_table.insert(candidate)
    return candidate


@router.get("")
def list_candidates(_: dict = Depends(get_current_user), q: str = "", status: str = "all", stage: str = "all", page: int = 1):
    records = candidates_table.all()
    query = q.strip().lower()
    records = [item for item in records if (not query or query in item["companyName"].lower() or query in item["corporateEmail"].lower()) and (status == "all" or item["status"] == status) and (stage == "all" or item["stage"] == stage)]
    page = max(1, page)
    start = (page - 1) * 5
    return {"data": records[start:start + 5], "page": page, "pageSize": 5, "total": len(records), "totalPages": max(1, (len(records) + 4) // 5)}


@router.get("/{candidate_id}")
def read_candidate(candidate_id: str, _: dict = Depends(get_current_user)):
    candidate = get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate was not found")
    return candidate


@router.patch("/{candidate_id}")
def patch_candidate(candidate_id: str, payload: CandidatePatch, _: dict = Depends(get_current_user)):
    candidate = get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate was not found")
    updates = payload.model_dump(exclude_none=True)
    updates["updatedAt"] = now()
    candidates_table.update(updates, Query().id == candidate_id)
    return get_candidate(candidate_id)


@router.put("/{candidate_id}")
def replace_candidate(candidate_id: str, payload: CandidateWrite, _: dict = Depends(get_current_user)):
    if not get_candidate(candidate_id):
        raise HTTPException(status_code=404, detail="Candidate was not found")
    candidates_table.update({**payload.model_dump(), "updatedAt": now()}, Query().id == candidate_id)
    return get_candidate(candidate_id)


@router.post("/{candidate_id}/notes", status_code=201)
def add_note(candidate_id: str, payload: NoteCreate, _: dict = Depends(get_current_user)):
    candidate = get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate was not found")
    note = {"id": f"note-{uuid4()}", "body": payload.body.strip(), "createdAt": now()}
    candidates_table.update({"notes": [note, *candidate.get("notes", [])], "updatedAt": now()}, Query().id == candidate_id)
    return get_candidate(candidate_id)


@router.delete("/{candidate_id}/notes/{note_id}")
def delete_note(candidate_id: str, note_id: str, _: dict = Depends(get_current_user)):
    candidate = get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate was not found")
    notes = candidate.get("notes", [])
    if not any(note["id"] == note_id for note in notes):
        raise HTTPException(status_code=404, detail="Note was not found")
    candidates_table.update({"notes": [note for note in notes if note["id"] != note_id], "updatedAt": now()}, Query().id == candidate_id)
    return get_candidate(candidate_id)
