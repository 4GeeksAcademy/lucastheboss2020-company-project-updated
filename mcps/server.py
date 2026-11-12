"""OAuth-protected Streamable HTTP MCP server exposing TrackFlow company tools."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import time
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

import uvicorn
from fastapi import FastAPI
from mcpauth import MCPAuth
from mcpauth.config import AuthServerConfig, AuthServerType, AuthorizationServerMetadata
from mcpauth.exceptions import MCPAuthTokenVerificationException, MCPAuthTokenVerificationExceptionCode
from mcpauth.utils import create_verify_jwt
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ValidationError
from starlette.responses import JSONResponse

from mcps.backend import BackendToolError, TrackFlowBackendClient
from mcps.config import MCPSettings, SCOPES
from services.incidents.manager_models import IncidentBranch, IncidentCategory, IncidentCreate, IncidentOrigin, IncidentStatus
from services.schemas import Category as InventoryCategory
from services.schemas import Warehouse

logger = logging.getLogger("mcps.audit")
# Direct handler: survives uvicorn's dictConfig and doesn't depend on root
# logger propagation. The handler is added only once (first import wins).
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(logging.INFO)
    _handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # we handle emission ourselves
TOOL_SCOPES = {
    "create_incident": "incidents:write",
    "update_incident_status": "incidents:write",
    "get_incident": "incidents:read",
    "query_inventory": "inventory:read",
}


class ToolError(BaseModel):
    code: str
    message: str
    status: int


class ToolResult(BaseModel):
    """MCP discovery and runtime serialization share this result schema."""

    ok: bool
    data: dict | list[dict] | None = None
    error: ToolError | None = None
    count: int | None = None
    read_only: bool | None = None


def _error(code: str, message: str, status_code: int) -> ToolResult:
    return ToolResult(ok=False, error=ToolError(code=code, message=message, status=status_code))


class ToolScopeMiddleware:
    """Check a verified bearer token's per-tool scope before MCP dispatch."""

    def __init__(self, app, *, auth: MCPAuth):
        self.app = app
        self.auth = auth

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        request_messages = []
        body = bytearray()
        while True:
            message = await receive()
            request_messages.append(message)
            if message["type"] == "http.request":
                body.extend(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            else:
                break

        try:
            payload = json.loads(body) if body else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = None
        requests = payload if isinstance(payload, list) else [payload]
        for item in requests:
            if not isinstance(item, dict) or item.get("method") != "tools/call":
                continue
            params = item.get("params")
            if not isinstance(params, dict) or not isinstance(params.get("name"), str) or not isinstance(params.get("arguments", {}), dict):
                info = self.auth.auth_info
                logger.info("mcp_tool_invocation client_id=%s tool=invalid-call result=invalid_params", info.client_id if info and info.client_id else "unknown-client")
                response = JSONResponse({"jsonrpc": "2.0", "id": item.get("id"), "error": {"code": -32602, "message": "Invalid tool call parameters."}}, status_code=400)
                await response(scope, receive, send)
                return

        required_scopes = {
            TOOL_SCOPES.get(item.get("params", {}).get("name"))
            for item in requests
            if isinstance(item, dict) and item.get("method") == "tools/call"
        }
        required_scopes.discard(None)
        verified = self.auth.auth_info
        missing = sorted(scope_name for scope_name in required_scopes if verified is None or scope_name not in verified.scopes)
        if missing:
            required = " ".join(missing)
            client_id = verified.client_id if verified and verified.client_id else "unknown-client"
            tool_name = next(
                (item.get("params", {}).get("name") for item in requests if isinstance(item, dict) and item.get("method") == "tools/call"),
                "unknown-tool",
            )
            logger.info("mcp_tool_invocation client_id=%s tool=%s result=insufficient_scope", client_id, tool_name)
            response = JSONResponse(
                {"error": {"code": "insufficient_scope", "required_scope": required}},
                status_code=403,
                headers={"WWW-Authenticate": f'Bearer error="insufficient_scope", scope="{required}"'},
            )
            await response(scope, receive, send)
            return

        allowed_inventory_fields = {"query", "sku", "client_name", "category", "warehouse", "limit", "operation"}
        for item in requests:
            if not isinstance(item, dict) or item.get("method") != "tools/call":
                continue
            params = item.get("params")
            if not isinstance(params, dict) or params.get("name") != "query_inventory":
                continue
            arguments = params.get("arguments", {})
            if isinstance(arguments, dict) and set(arguments) - allowed_inventory_fields:
                logger.info(
                    "mcp_tool_invocation client_id=%s tool=query_inventory result=read_only",
                    verified.client_id if verified and verified.client_id else "unknown-client",
                )
                response = JSONResponse(
                    _error("read_only", "Inventory requests cannot contain write or unsupported fields.", 405).model_dump(mode="json"),
                    status_code=400,
                )
                await response(scope, receive, send)
                return

        message_index = 0

        async def replay_receive():
            nonlocal message_index
            if message_index < len(request_messages):
                message = request_messages[message_index]
                message_index += 1
                return message
            return await receive()

        response_body = bytearray()
        response_status = 200

        async def send_with_result_audit(message):
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
            if message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if len(response_body) + len(chunk) <= 1_048_576:
                    response_body.extend(chunk)
                if not message.get("more_body", False):
                    outcome = f"http_{response_status}"
                    text = response_body.decode("utf-8", errors="replace")
                    candidates = [line[6:] for line in text.splitlines() if line.startswith("data: ")] or [text]
                    for candidate in candidates:
                        try:
                            packet = json.loads(candidate)
                        except (ValueError, TypeError):
                            continue
                        if not isinstance(packet, dict):
                            continue
                        result = packet.get("result")
                        if packet.get("error") or (isinstance(result, dict) and result.get("isError")):
                            outcome = "tool_error"
                    for item in requests:
                        if isinstance(item, dict) and item.get("method") == "tools/call":
                            name = item["params"]["name"]
                            logger.info("mcp_tool_result client_id=%s tool=%s result=%s", verified.client_id if verified and verified.client_id else "unknown-client", name if name in TOOL_SCOPES else "unknown-tool", outcome)
            await send(message)

        await self.app(scope, replay_receive, send_with_result_audit)


class ProtectedResourceMetadataApp:
    """Serve RFC 9728 metadata without auth; all other paths reach the protected MCP app."""

    def __init__(self, app, settings: MCPSettings):
        self.app = app
        self.settings = settings
        self.paths = {
            "/.well-known/oauth-protected-resource",
            "/.well-known/oauth-protected-resource/mcp",
        }

    @staticmethod
    def _static_cors_headers() -> dict:
        return {
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept",
            "Access-Control-Max-Age": "600",
        }

    def _cors_for_request(self, scope) -> dict:
        """Return CORS headers appropriate for the request origin.

        - No Origin header → wildcard (public discovery).
        - Origin in allowed_origins → echo the origin with Vary: Origin.
        - Origin not in allowed_origins → no ACAO header (rejected).
        """
        origin = ""
        for key, value in scope.get("headers", []):
            if key.lower() == b"origin":
                origin = value.decode("ascii", errors="replace")
                break
        if not origin:
            return {"Access-Control-Allow-Origin": "*"}
        if origin in self.settings.allowed_origins:
            return {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
        return {}

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("method") in {"GET", "HEAD", "OPTIONS"} and scope.get("path") in self.paths:
            merged = dict(ProtectedResourceMetadataApp._static_cors_headers())
            cors = self._cors_for_request(scope)
            merged.update(cors)
            if scope.get("method") == "OPTIONS":
                await JSONResponse("", status_code=204, headers=merged)(scope, receive, send)
                return
            merged["Cache-Control"] = "public, max-age=60"
            body = {
                "resource": self.settings.resource_url,
                "authorization_servers": [self.settings.issuer],
                "scopes_supported": list(SCOPES),
                "bearer_methods_supported": ["header"],
            }
            await JSONResponse(body, headers=merged)(scope, receive, send)
            return
        async def send_with_challenge(message):
            if message["type"] == "http.response.start" and message["status"] == 401:
                parsed = urlsplit(self.settings.resource_url)
                metadata_url = f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-protected-resource{parsed.path.rstrip('/')}"
                headers = list(message.get("headers", []))
                headers = [(key, value) for key, value in headers if key.lower() != b"www-authenticate"]
                headers.append((b"www-authenticate", f'Bearer resource_metadata="{metadata_url}"'.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_challenge)


def create_mcp_app(
    settings: MCPSettings,
    backend: TrackFlowBackendClient | None = None,
    token_verifier: Literal["jwt"] | object = "jwt",
):
    """Create a fail-closed Streamable HTTP MCP ASGI app; injectable for local tests."""
    metadata = AuthorizationServerMetadata(
        issuer=settings.issuer,
        authorization_endpoint=settings.authorization_url,
        token_endpoint=settings.token_url,
        jwks_uri=settings.jwks_url,
        scope_supported=list(SCOPES),
        response_types_supported=["code"],
        response_modes_supported=["query"],
        grant_types_supported=["authorization_code", "refresh_token"],
        token_endpoint_auth_methods_supported=["client_secret_basic", "client_secret_post"],
        code_challenge_methods_supported=["S256"],
    )
    auth = MCPAuth(AuthServerConfig(metadata=metadata, type=AuthServerType.OAUTH))
    verify_token = create_verify_jwt(settings.jwks_url, leeway=0) if token_verifier == "jwt" else token_verifier

    def verify_with_required_expiry(token: str):
        info = verify_token(token)
        expiry = info.claims.get("exp")
        if isinstance(expiry, bool) or not isinstance(expiry, (int, float)) or not math.isfinite(expiry) or expiry <= time.time():
            raise MCPAuthTokenVerificationException(MCPAuthTokenVerificationExceptionCode.INVALID_TOKEN)
        return info

    api = backend or TrackFlowBackendClient(settings.backend_url, settings.backend_token)
    mcp = FastMCP(
        name="TrackFlow Company Tools",
        instructions=(
            "Use tools only for TrackFlow incident lifecycle operations and read-only inventory queries. "
            "Never modify inventory. Follow each tool's documented scope and schema."
        ),
        host=settings.host,
        port=settings.port,
        mount_path="/mcp",
        streamable_http_path="/mcp",
        stateless_http=True,
    )

    def audit(tool_name: str, outcome: str) -> None:
        info = auth.auth_info
        client_id = info.client_id if info and info.client_id else "unknown-client"
        logger.info(
            "mcp_tool_invocation client_id=%s tool=%s result=%s",
            client_id,
            tool_name,
            outcome,
        )

    def tool_error(tool_name: str, error: BackendToolError) -> ToolResult:
        audit(tool_name, error.code)
        return _error(error.code, error.safe_message, error.status_code)

    @mcp.tool()
    async def create_incident(
        title: str,
        description: str,
        category: IncidentCategory,
        origin: IncidentOrigin,
        branch: IncidentBranch,
    ) -> ToolResult:
        """Create a TrackFlow incident with title, description, category, origin, and branch."""
        try:
            incident = IncidentCreate(
                title=title,
                description=description,
                category=category,
                origin=origin,
                branch=branch,
            )
        except ValidationError as error:
            first = error.errors()[0]
            field = str(first.get("loc", ["payload"])[-1])
            audit("create_incident", "invalid_input")
            return _error("invalid_input", f"Invalid incident field: {field}.", 400)
        try:
            result = await api.create_incident(incident.model_dump(mode="json"))
        except BackendToolError as error:
            return tool_error("create_incident", error)
        audit("create_incident", "created")
        return ToolResult(ok=True, data=result)

    @mcp.tool()
    async def update_incident_status(incident_id: str, status: IncidentStatus) -> ToolResult:
        """Transition an incident using only PATCH /api/incidents/{id}/status and the official lifecycle."""
        try:
            incident_id = str(UUID(incident_id))
        except ValueError:
            audit("update_incident_status", "invalid_input")
            return _error("invalid_input", "incident_id must be a UUID.", 400)
        try:
            result = await api.update_incident_status(incident_id, status.value)
        except BackendToolError as error:
            return tool_error("update_incident_status", error)
        audit("update_incident_status", "updated")
        return ToolResult(ok=True, data=result)

    @mcp.tool()
    async def get_incident(incident_id: str) -> ToolResult:
        """Get one TrackFlow incident by its UUID."""
        try:
            incident_id = str(UUID(incident_id))
        except ValueError:
            audit("get_incident", "invalid_input")
            return _error("invalid_input", "incident_id must be a UUID.", 400)
        try:
            result = await api.get_incident(incident_id)
        except BackendToolError as error:
            return tool_error("get_incident", error)
        audit("get_incident", "success")
        return ToolResult(ok=True, data=result)

    @mcp.tool()
    async def query_inventory(
        query: str = "",
        sku: str | None = None,
        client_name: str | None = None,
        category: InventoryCategory | None = None,
        warehouse: Warehouse | None = None,
        limit: int = 20,
        operation: str = "read",
    ) -> ToolResult:
        """Read and filter inventory by text/SKU/client/category/warehouse; operation must be 'read'."""
        if operation.casefold() != "read" or re.search(
            r"\b(?:update|modify|change|edit|delete|remove|adjust|increase|decrease|add|set|write|restock)\b",
            query,
            re.IGNORECASE,
        ):
            audit("query_inventory", "write_rejected")
            return _error("read_only", "Inventory is read-only through MCP; write or modification attempts are rejected.", 405)
        if not 1 <= limit <= 100:
            audit("query_inventory", "invalid_input")
            return _error("invalid_input", "limit must be between 1 and 100.", 400)
        try:
            products = await api.list_inventory()
        except BackendToolError as error:
            return tool_error("query_inventory", error)

        text_query = query.strip().casefold()
        matches = []
        for product in products:
            if sku and str(product.get("sku", "")).casefold() != sku.strip().casefold():
                continue
            if client_name and str(product.get("client_name", "")).casefold() != client_name.strip().casefold():
                continue
            if category and product.get("category") != category:
                continue
            if warehouse and product.get("warehouse") != warehouse:
                continue
            if text_query and text_query not in " ".join(
                str(product.get(key, "")) for key in ("name", "sku", "client_name", "category", "warehouse")
            ).casefold():
                continue
            matches.append(
                {
                    key: product.get(key)
                    for key in ("id", "name", "sku", "client_name", "category", "warehouse", "current_stock")
                }
            )
            if len(matches) >= limit:
                break
        audit("query_inventory", "success")
        return ToolResult(ok=True, data=matches, count=len(matches), read_only=True)

    mcp_app = mcp.streamable_http_app()
    # Starlette add_middleware wraps: last-added = outermost.
    # Correct stack (outermost → innermost):
    #   1. CORS (so OPTIONS preflight never hits auth)
    #   2. bearer_auth (rejects unauthenticated → 401)
    #   3. ToolScope (checks scopes on authenticated requests → 403)
    #   4. Streamable HTTP app (innermost)
    ToolScopeMiddleware  # keep import alive
    mcp_app.add_middleware(ToolScopeMiddleware, auth=auth)
    mcp_app.add_middleware(
        auth.bearer_auth_middleware(
            verify_with_required_expiry,
            audience=settings.audience,
            required_scopes=["mcp:connect"],
            show_error_details=False,
            leeway=0,
        )
    )
    if settings.allowed_origins:
        from starlette.middleware.cors import CORSMiddleware
        mcp_app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.allowed_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS", "HEAD", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "Accept", "MCP-Protocol-Version", "MCP-Session-Id", "Last-Event-ID"],
            expose_headers=["WWW-Authenticate", "MCP-Session-Id"],
            max_age=600,
        )
    return ProtectedResourceMetadataApp(mcp_app, settings)


def main() -> None:
    settings = MCPSettings.from_env()
    app = create_mcp_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
