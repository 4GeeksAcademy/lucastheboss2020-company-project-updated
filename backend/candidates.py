from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from tinydb import Query
from .auth import get_current_user
from .models import CandidatePatch, CandidateWrite, NoteCreate
from .storage import candidates_table

router = APIRouter(prefix="/candidates", tags=["candidates"])

UserDep = Depends(get_current_user)


@router.get("/")
def list_candidates(_user: dict = UserDep):
    return candidates_table.all()


@router.get("/{candidate_id}")
def get_candidate(candidate_id: str, _user: dict = UserDep):
    record = candidates_table.get(Query().id == candidate_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    return record


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_candidate(payload: CandidateWrite, _user: dict = UserDep):
    now = datetime.now(timezone.utc).isoformat()
    record = payload.model_dump()
    record["id"] = str(uuid4())
    record["notes"] = []
    record["createdAt"] = now
    record["updatedAt"] = now
    candidates_table.insert(record)
    return record


@router.patch("/{candidate_id}")
def patch_candidate(candidate_id: str, payload: CandidatePatch, _user: dict = UserDep):
    record = candidates_table.get(Query().id == candidate_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    updates = payload.model_dump(exclude_none=True)
    updates["updatedAt"] = datetime.now(timezone.utc).isoformat()
    candidates_table.update(updates, Query().id == candidate_id)
    return candidates_table.get(Query().id == candidate_id)


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(candidate_id: str, _user: dict = UserDep):
    record = candidates_table.get(Query().id == candidate_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    candidates_table.remove(Query().id == candidate_id)


@router.get("/{candidate_id}/notes")
def list_notes(candidate_id: str, _user: dict = UserDep):
    record = candidates_table.get(Query().id == candidate_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    return record.get("notes", [])


@router.post("/{candidate_id}/notes", status_code=status.HTTP_201_CREATED)
def add_note(candidate_id: str, payload: NoteCreate, _user: dict = UserDep):
    record = candidates_table.get(Query().id == candidate_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    note = {
        "id": str(uuid4()),
        "body": payload.body,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    notes = record.get("notes", [])
    notes.append(note)
    candidates_table.update({"notes": notes, "updatedAt": datetime.now(timezone.utc).isoformat()}, Query().id == candidate_id)
    return note


@router.delete("/{candidate_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(candidate_id: str, note_id: str, _user: dict = UserDep):
    record = candidates_table.get(Query().id == candidate_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
    notes = record.get("notes", [])
    filtered = [n for n in notes if n.get("id") != note_id]
    if len(filtered) == len(notes):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found.")
    candidates_table.update({"notes": filtered, "updatedAt": datetime.now(timezone.utc).isoformat()}, Query().id == candidate_id)