"""Narrow HTTP client for the existing incident and inventory APIs."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class BackendToolError(RuntimeError):
    code: str
    safe_message: str
    status_code: int

    def __str__(self) -> str:
        return self.safe_message


class TrackFlowBackendClient:
    """Uses only the existing incident lifecycle and inventory read endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        bearer_token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("MCP_BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")
        self._bearer_token = bearer_token if bearer_token is not None else os.getenv("MCP_BACKEND_TOKEN", "")
        self._transport = transport

    async def request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        method = method.upper()
        permitted = (
            method == "POST" and path == "/api/incidents"
        ) or (
            method == "GET" and (path == "/inventory/products" or re.fullmatch(r"/api/incidents/[0-9a-fA-F-]{36}", path))
        ) or (
            method == "PATCH" and re.fullmatch(r"/api/incidents/[0-9a-fA-F-]{36}/status", path)
        )
        if not permitted:
            raise BackendToolError(
                "operation_not_allowed",
                "This MCP server permits only incident create/read/status transitions and inventory reads.",
                405,
            )
        if method == "POST" and payload is not None and set(payload) != {"title", "description", "category", "origin", "branch"}:
            raise BackendToolError("invalid_input", "Incident fields do not match the allowed schema.", 400)
        if method == "PATCH" and (payload is None or set(payload) != {"status"}):
            raise BackendToolError("invalid_input", "Only the incident status field may be updated.", 400)
        if method == "GET" and path == "/inventory/products" and payload is not None:
            raise BackendToolError("read_only", "Inventory requests are read-only and do not accept write payloads.", 405)
        if not self._bearer_token:
            raise BackendToolError(
                "backend_auth_not_configured",
                "MCP_BACKEND_TOKEN is not configured for the internal TrackFlow API.",
                503,
            )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self._bearer_token}"},
                timeout=10.0,
                transport=self._transport,
            ) as client:
                response = await client.request(method, path, json=payload)
        except httpx.RequestError as error:
            raise BackendToolError("backend_unavailable", "The TrackFlow API is unavailable.", 503) from error

        if response.status_code < 400:
            try:
                return response.json()
            except ValueError as error:
                raise BackendToolError("invalid_backend_response", "The TrackFlow API returned an invalid response.", 502) from error

        if response.status_code == 404:
            raise BackendToolError("not_found", "The requested TrackFlow record was not found.", 404)
        if response.status_code == 405:
            raise BackendToolError("read_only", "This operation is not permitted by the TrackFlow API.", 405)
        if response.status_code == 422:
            raise BackendToolError("validation_error", "The request does not match the TrackFlow API schema.", 422)
        if response.status_code == 400:
            error = "invalid_status_transition" if method.upper() == "PATCH" and path.endswith("/status") else "validation_error"
            message = "The incident status transition is not allowed." if error == "invalid_status_transition" else "The request does not match the TrackFlow API schema."
            raise BackendToolError(error, message, 400)
        if response.status_code in (401, 403):
            raise BackendToolError("backend_unauthorized", "The configured backend service token was rejected.", response.status_code)
        raise BackendToolError("backend_error", "The TrackFlow API could not complete the operation.", 502)

    async def create_incident(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request_json("POST", "/api/incidents", payload)

    async def update_incident_status(self, incident_id: str, status: str) -> dict[str, Any]:
        return await self.request_json("PATCH", f"/api/incidents/{incident_id}/status", {"status": status})

    async def get_incident(self, incident_id: str) -> dict[str, Any]:
        return await self.request_json("GET", f"/api/incidents/{incident_id}")

    async def list_inventory(self) -> list[dict[str, Any]]:
        result = await self.request_json("GET", "/inventory/products")
        if not isinstance(result, list):
            raise BackendToolError("invalid_backend_response", "The inventory API returned an invalid response.", 502)
        return result
