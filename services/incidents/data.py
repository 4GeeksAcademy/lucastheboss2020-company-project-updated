"""
In-memory storage for TRF incident analysis results.
Analogy to services/suppliers/data.py but for analysis results.
"""

from datetime import datetime
from typing import Optional
import uuid

# In-memory store: dict of AnalysisResult-like dicts keyed by ID
_store: dict[str, dict] = {}


def store_analysis(result: dict) -> dict:
    """Store an analysis result and return it with generated id/timestamp."""
    analysis_id = str(uuid.uuid4())
    timestamp = int(datetime.utcnow().timestamp() * 1000)

    record = {
        "id": analysis_id,
        "timestamp": timestamp,
        **result,
    }
    _store[analysis_id] = record
    return record


def get_analysis(analysis_id: str) -> Optional[dict]:
    """Retrieve an analysis result by ID."""
    return _store.get(analysis_id)


def get_all_analyses() -> list[dict]:
    """Get all stored analysis results."""
    return list(_store.values())


def delete_analysis(analysis_id: str) -> bool:
    """Delete an analysis result by ID. Returns True if found."""
    if analysis_id in _store:
        del _store[analysis_id]
        return True
    return False