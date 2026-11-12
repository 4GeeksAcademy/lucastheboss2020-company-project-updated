"""Readiness command for the TrackFlow MCP server.

Usage:
    python -m mcps.tools.check_readiness

Prints only:
  - Setting NAMES that are missing (never values/secrets)
  - BOOLEAN pass/fail per check
  - Aggregate "ready: true/false"

Exits 0 if ready, 1 otherwise.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass


@dataclass
class ReadinessCheck:
    name: str
    present: bool
    detail: str = ""


_REQUIRED = [
    "MCP_OAUTH_ISSUER",
    "MCP_OAUTH_AUTHORIZATION_URL",
    "MCP_OAUTH_TOKEN_URL",
    "MCP_OAUTH_JWKS_URL",
    "MCP_OAUTH_AUDIENCE",
    "MCP_RESOURCE_URL",
    "MCP_BACKEND_URL",
]

_RECOMMENDED = [
    "MCP_BACKEND_TOKEN",
    "JWT_SECRET_KEY",
]


def check() -> list[ReadinessCheck]:
    results: list[ReadinessCheck] = []

    for var_name in _REQUIRED:
        value = os.getenv(var_name, "").strip()
        if not value:
            results.append(ReadinessCheck(name=var_name, present=False, detail="missing"))
        else:
            results.append(ReadinessCheck(name=var_name, present=True))

    for var_name in _RECOMMENDED:
        value = os.getenv(var_name, "").strip()
        if not value:
            results.append(ReadinessCheck(name=var_name, present=False, detail="recommended but missing"))
        else:
            results.append(ReadinessCheck(name=var_name, present=True))

    return results


def main() -> int:
    checks = check()
    all_required_present = all(
        c.present for c in checks if c.name in _REQUIRED
    )
    missing_required = [c.name for c in checks if not c.present and c.name in _REQUIRED]

    if all_required_present:
        print("ready: true")
    else:
        print("ready: false")

    if missing_required:
        print(f"missing ({len(missing_required)}):")
        for name in missing_required:
            print(f"  - {name}")

    recommended_missing = [c.name for c in checks if not c.present and c.name in _RECOMMENDED]
    if recommended_missing:
        print(f"recommended ({len(recommended_missing)}):")
        for name in recommended_missing:
            print(f"  - {name} (optional)")

    return 0 if all_required_present else 1


if __name__ == "__main__":
    sys.exit(main())