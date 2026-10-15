import logging
from typing import Any

from backend.auth import get_current_user
from backend.telemetry.inventory_events import (
    emit_inventory_discrepancy_detected,
    inventory_context,
)
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from . import manager_data
from .manager_data import InvalidStatusTransition
from .manager_models import (
    IncidentBranch,
    IncidentCategory,
    IncidentCreate,
    IncidentListItem,
    IncidentOrigin,
    IncidentResponse,
    IncidentStatus,
    IncidentSummaryResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

FILTER_ENUMS = {
    "status": IncidentStatus,
    "origin": IncidentOrigin,
    "branch": IncidentBranch,
    "category": IncidentCategory,
}

FIELD_ERRORS = {
    "title": "Title is required and must be no longer than 120 characters.",
    "description": "Description is required.",
    "category": "Select a valid incident category.",
    "origin": "Select a valid incident origin.",
    "branch": "Select a valid TrackFlow branch.",
}


def _validation_response(error: ValidationError) -> JSONResponse:
    issue = error.errors()[0]
    field = str(issue.get("loc", ["payload"])[-1])
    return JSONResponse(
        {"error": {"field": field, "message": FIELD_ERRORS.get(field, "Check this field and try again.")}},
        status_code=400,
    )


def _internal_error() -> JSONResponse:
    logger.error("Incident manager request failed unexpectedly")
    return JSONResponse(
        {"error": {"message": "The incident request could not be completed. Please try again."}},
        status_code=500,
    )


async def _json_body(request: Request) -> dict[str, Any] | JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"error": {"field": "body", "message": "Request body must be valid JSON."}},
            status_code=400,
        )
    if not isinstance(body, dict):
        return JSONResponse(
            {"error": {"field": "body", "message": "Request body must be a JSON object."}},
            status_code=400,
        )
    return body


@router.get("/api/incidents", response_model=list[IncidentListItem])
def list_manager_incidents(
    status: str | None = None,
    origin: str | None = None,
    branch: str | None = None,
    category: str | None = None,
    _user: dict = Depends(get_current_user),
):
    filters = {"status": status, "origin": origin, "branch": branch, "category": category}
    for field, value in filters.items():
        if value is not None and value not in {item.value for item in FILTER_ENUMS[field]}:
            return JSONResponse(
                {"error": {"field": field, "message": f"Select a valid incident {field}."}},
                status_code=400,
            )
    try:
        return manager_data.list_incidents(**filters)
    except Exception:
        return _internal_error()


@router.post("/api/incidents", response_model=IncidentResponse, status_code=201)
async def create_manager_incident(
    request: Request,
    user: dict = Depends(get_current_user),
):
    body = await _json_body(request)
    if isinstance(body, JSONResponse):
        return body
    try:
        payload = IncidentCreate.model_validate(body)
        record = manager_data.create_incident(payload)
        # MANDATORY (CONTEXT_6 §5): inventory_discrepancy_detected when a stock
        # discrepancy incident is reported.
        if payload.category == IncidentCategory.INVENTORY_DISCREPANCY:
            emit_inventory_discrepancy_detected(
                context=inventory_context(warehouse=payload.branch.value, client_name=payload.title),
                system_stock=0,
                physical_stock=0,
                audit_reference=record["id"],
                user_id=user.get("id"),
            )
        return record
    except ValidationError as error:
        return _validation_response(error)
    except Exception:
        return _internal_error()


@router.get("/api/incidents/summary", response_model=IncidentSummaryResponse)
def get_manager_summary(_user: dict = Depends(get_current_user)):
    try:
        return manager_data.get_summary()
    except Exception:
        return _internal_error()


@router.get("/api/incidents/{incident_id}", response_model=IncidentResponse)
def get_manager_incident(
    incident_id: str,
    _user: dict = Depends(get_current_user),
):
    try:
        record = manager_data.get_incident(incident_id)
        if record is None:
            return JSONResponse(
                {"error": {"message": "Incident not found."}},
                status_code=404,
            )
        return record
    except Exception:
        return _internal_error()


@router.patch("/api/incidents/{incident_id}/status", response_model=IncidentResponse)
async def update_manager_incident_status(
    incident_id: str,
    request: Request,
    _user: dict = Depends(get_current_user),
):
    body = await _json_body(request)
    if isinstance(body, JSONResponse):
        return body
    try:
        payload_status = IncidentStatus(body.get("status"))
    except (TypeError, ValueError):
        return JSONResponse(
            {"error": {"field": "status", "message": "Select a valid incident status."}},
            status_code=400,
        )

    try:
        record = manager_data.update_incident_status(incident_id, payload_status)
        if record is None:
            return JSONResponse(
                {"error": {"message": "Incident not found."}},
                status_code=404,
            )
        return record
    except InvalidStatusTransition as error:
        return JSONResponse(
            {"error": {"field": "status", "message": str(error)}},
            status_code=400,
        )
    except Exception:
        return _internal_error()
