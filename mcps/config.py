"""Fail-closed OAuth and backend settings for the TrackFlow MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


class MCPConfigurationError(RuntimeError):
    """Required OAuth resource-server configuration is missing or unsafe."""


SCOPES = (
    "mcp:connect",
    "incidents:read",
    "incidents:write",
    "inventory:read",
)


def _required_url(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise MCPConfigurationError(f"Set {name} in the MCP server environment.")
    parsed = urlparse(value)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username or parsed.password:
        raise MCPConfigurationError(f"{name} must be an absolute HTTP(S) URL without embedded credentials.")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise MCPConfigurationError(f"{name} must use HTTPS except for loopback-only local development.")
    return value.rstrip("/")


@dataclass(frozen=True)
class MCPSettings:
    issuer: str
    authorization_url: str
    token_url: str
    jwks_url: str
    audience: str
    resource_url: str
    backend_url: str
    backend_token: str | None
    host: str
    port: int
    allowed_origins: tuple[str, ...] = ()

    @classmethod
    def from_env(cls) -> "MCPSettings":
        required_strings = {
            "MCP_OAUTH_ISSUER": _required_url("MCP_OAUTH_ISSUER"),
            "MCP_OAUTH_AUTHORIZATION_URL": _required_url("MCP_OAUTH_AUTHORIZATION_URL"),
            "MCP_OAUTH_TOKEN_URL": _required_url("MCP_OAUTH_TOKEN_URL"),
            "MCP_OAUTH_JWKS_URL": _required_url("MCP_OAUTH_JWKS_URL"),
            "MCP_RESOURCE_URL": _required_url("MCP_RESOURCE_URL"),
        }
        resource_url = required_strings["MCP_RESOURCE_URL"]
        audience = os.getenv("MCP_OAUTH_AUDIENCE", "").strip()
        if not audience:
            raise MCPConfigurationError("Set MCP_OAUTH_AUDIENCE in the MCP server environment.")
        if audience.rstrip("/") != resource_url:
            raise MCPConfigurationError(
                "MCP_OAUTH_AUDIENCE must match MCP_RESOURCE_URL exactly to keep RFC 9728 resource "
                "identifiers consistent with JWT audience validation."
            )
        port_text = os.getenv("MCP_PORT", "8001")
        try:
            port = int(port_text)
        except ValueError as error:
            raise MCPConfigurationError("MCP_PORT must be an integer.") from error
        if not 1 <= port <= 65535:
            raise MCPConfigurationError("MCP_PORT must be between 1 and 65535.")

        raw = os.getenv("MCP_ALLOWED_ORIGINS", "").strip()
        allowed_origins = tuple(o.strip() for o in raw.split(",") if o.strip()) if raw else ()

        return cls(
            issuer=required_strings["MCP_OAUTH_ISSUER"],
            authorization_url=required_strings["MCP_OAUTH_AUTHORIZATION_URL"],
            token_url=required_strings["MCP_OAUTH_TOKEN_URL"],
            jwks_url=required_strings["MCP_OAUTH_JWKS_URL"],
            audience=audience,
            resource_url=resource_url,
            backend_url=os.getenv("MCP_BACKEND_URL", "http://127.0.0.1:8000").strip().rstrip("/"),
            backend_token=os.getenv("MCP_BACKEND_TOKEN", "").strip() or None,
            host=os.getenv("MCP_HOST", "127.0.0.1").strip(),
            port=port,
            allowed_origins=allowed_origins,
        )
