"""Config validator entrypoint for the TrackFlow MCP server.

Usage:
    python -m mcps.tools.validate_config

Checks all required environment variables and prints only the NAMES of
missing settings and BOOLEAN pass/fail per check — never values or secrets.
Exits 0 if all required variables are present and valid, 1 otherwise.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


_REQUIRED_VARS: dict[str, str] = {
    "MCP_OAUTH_ISSUER": "OAuth provider issuer URL (https)",
    "MCP_OAUTH_AUTHORIZATION_URL": "OAuth authorize endpoint",
    "MCP_OAUTH_TOKEN_URL": "OAuth token endpoint",
    "MCP_OAUTH_JWKS_URL": "JWKS public-key set URL",
    "MCP_OAUTH_AUDIENCE": "JWT audience (must match MCP_RESOURCE_URL)",
    "MCP_RESOURCE_URL": "Public resource URL for this MCP server",
    "MCP_BACKEND_URL": "Internal TrackFlow API base URL",
}

_OPTIONAL_VARS: dict[str, str] = {
    "MCP_BACKEND_TOKEN": "Bearer token for internal TrackFlow API",
    "MCP_ALLOWED_ORIGINS": "Comma-separated CORS origins (browser Playground)",
    "MCP_PORT": "HTTP listen port (default 8001)",
    "MCP_HOST": "HTTP bind address (default 127.0.0.1)",
}


def _check_url(name: str, value: str) -> str | None:
    """Return error message if the value is not a valid HTTPS (or loopback HTTP) URL."""
    if not value.strip():
        return f"{name} is empty"
    parsed = urlparse(value)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        return f"{name} must be an absolute HTTP(S) URL"
    if parsed.username or parsed.password:
        return f"{name} must not contain embedded credentials"
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return f"{name} must use HTTPS except for loopback"
    return None


def run_checks() -> list[CheckResult]:
    results: list[CheckResult] = []

    # --- Required vars present? ---
    for var_name, hint in _REQUIRED_VARS.items():
        raw = os.getenv(var_name, "").strip()
        if not raw:
            results.append(CheckResult(name=var_name, passed=False, detail=f"MISSING — {hint}"))
            continue
        error = _check_url(var_name, raw)
        if error:
            results.append(CheckResult(name=var_name, passed=False, detail=error))
        else:
            results.append(CheckResult(name=var_name, passed=True, detail="present"))

    # --- Audience == Resource URL consistency ---
    audience = os.getenv("MCP_OAUTH_AUDIENCE", "").strip().rstrip("/")
    resource_url = os.getenv("MCP_RESOURCE_URL", "").strip().rstrip("/")
    if audience and resource_url and audience != resource_url:
        results.append(
            CheckResult(
                name="MCP_OAUTH_AUDIENCE",
                passed=False,
                detail=f"MISMATCH: audience='{audience}' != resource_url='{resource_url}'",
            )
        )

    # --- MCP_BACKEND_TOKEN (optional but recommended) ---
    token = os.getenv("MCP_BACKEND_TOKEN", "")
    if not token:
        results.append(CheckResult(name="MCP_BACKEND_TOKEN", passed=False, detail="MISSING — backend internal auth not configured"))
    else:
        results.append(CheckResult(name="MCP_BACKEND_TOKEN", passed=True, detail="present"))

    # --- Port ---
    port_raw = os.getenv("MCP_PORT", "8001")
    try:
        port = int(port_raw)
        if not 1 <= port <= 65535:
            results.append(CheckResult(name="MCP_PORT", passed=False, detail=f"out of range (1-65535): {port_raw}"))
        else:
            results.append(CheckResult(name="MCP_PORT", passed=True, detail=f"port {port}"))
    except ValueError:
        results.append(CheckResult(name="MCP_PORT", passed=False, detail=f"not an integer: {port_raw}"))

    # --- Allowed origins (optional) ---
    origins = os.getenv("MCP_ALLOWED_ORIGINS", "").strip()
    if origins:
        parts = [o.strip() for o in origins.split(",") if o.strip()]
        for origin in parts:
            error = _check_url("MCP_ALLOWED_ORIGINS entry", origin)
            if error:
                results.append(CheckResult(name=f"MCP_ALLOWED_ORIGINS ({origin})", passed=False, detail=error))
        if all(not r.name.startswith("MCP_ALLOWED_ORIGINS") or r.passed for r in results):
            results.append(CheckResult(name="MCP_ALLOWED_ORIGINS", passed=True, detail=f"{len(parts)} origin(s) configured"))
    else:
        results.append(CheckResult(name="MCP_ALLOWED_ORIGINS", passed=False, detail="not set — CORS disabled"))

    return results


def _summary_table(results: list[CheckResult]) -> list[str]:
    lines: list[str] = []
    lines.append("TrackFlow MCP Configuration Check")
    lines.append("=" * 50)
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"  [{status}]  {r.name}")
    lines.append("=" * 50)
    lines.append(f"  {passed} passed, {failed} failed")
    return lines


def main() -> int:
    results = run_checks()
    for line in _summary_table(results):
        print(line)
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())