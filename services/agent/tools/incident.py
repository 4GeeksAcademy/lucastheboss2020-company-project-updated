"""Typed, timeout-bounded incident lookup tool for the LangGraph agent.

Replaces the unbounded ``manager_data.get_incident()`` call with a
bounded wrapper that enforces a 5-second wall-clock timeout **without
waiting for hung workers** during cleanup.

Usage::

    from services.agent.tools.incident import (
        lookup_incident_by_id,
        IncidentLookupResponse,
    )
    result = lookup_incident_by_id("TRF-abc12345")
    # Returns IncidentLookupResponse | None — raises IncidentToolError if >5 s.

The module-level ``_WRAPPER_EXECUTOR`` is a ``ThreadPoolExecutor`` that
is **not** shut down on timeout — only the offending ``Future`` is
cancelled, so the worker thread (which may be stuck) is left running
without blocking the caller.
"""

from __future__ import annotations

import concurrent.futures
import logging
from typing import TypedDict

from services.incidents.manager_data import get_incident

logger = logging.getLogger(__name__)

# ── Default upper bound (seconds) ───────────────────────────────────────
INCIDENT_TIMEOUT = 5

# ── Reusable executor ───────────────────────────────────────────────────
# Using a module-level executor avoids the ``with`` statement whose
# ``shutdown(wait=True)`` would block on a hung worker even after we
# have already raised ``TimeoutError`` to the caller.
_WRAPPER_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# ======================================================================
# Typed field contracts
# ======================================================================


class IncidentLookupInput(TypedDict):
    """Input contract for the incident lookup tool."""

    incident_id: str


class IncidentLookupResponse(TypedDict, total=False):
    """Output contract matching the real incident record fields.

    All fields below are present when the incident exists; the function
    itself returns ``None`` to indicate "not found".
    """

    id: str
    title: str
    description: str
    category: str
    status: str
    origin: str
    branch: str
    created_at: str
    updated_at: str


# ======================================================================
# Tool error
# ======================================================================


class IncidentToolError(RuntimeError):
    """Raised when the incident tool times out or fails unexpectedly."""


# ======================================================================
# Bounded lookup
# ======================================================================


def lookup_incident_by_id(
    incident_id: str,
    *,
    timeout: float | None = None,
) -> IncidentLookupResponse | None:
    """Return the incident record for *incident_id*, or ``None`` if not found.

    Parameters
    ----------
    incident_id
        The unique identifier of the incident (e.g. ``"TRF-abc12345"``).
    timeout
        Optional per-call timeout in seconds.  Defaults to the module-level
        ``INCIDENT_TIMEOUT`` (5 s).  Used by tests to verify bounded
        behaviour with a short wall-clock deadline.

    Raises
    ------
    IncidentToolError
        If the call exceeds the timeout or fails unexpectedly.
    """
    effective_timeout = timeout if timeout is not None else INCIDENT_TIMEOUT

    future = _WRAPPER_EXECUTOR.submit(get_incident, incident_id)
    try:
        raw = future.result(timeout=effective_timeout)
    except concurrent.futures.TimeoutError:
        logger.error(
            "Incident lookup timed out after %s s for id=%r",
            effective_timeout,
            incident_id,
        )
        # Cancel the future so the caller is never blocked by a hung
        # worker; the module-level executor keeps running so we do not
        # call ``shutdown(wait=True)`` here.
        future.cancel()
        raise IncidentToolError(
            f"Incident lookup timed out after {effective_timeout} s for "
            f"{incident_id!r}"
        )
    except Exception as exc:
        logger.error("Incident lookup failed for id=%r: %s", incident_id, exc)
        raise IncidentToolError(
            f"Incident lookup failed for {incident_id!r}: {exc}"
        ) from exc

    if raw is None:
        return None

    # Map raw TinyDB row to typed output contract.
    return IncidentLookupResponse(
        id=str(raw.get("id", "")),
        title=str(raw.get("title", "")),
        description=str(raw.get("description", "")),
        category=str(raw.get("category", "")),
        status=str(raw.get("status", "")),
        origin=str(raw.get("origin", "")),
        branch=str(raw.get("branch", "")),
        created_at=str(raw.get("created_at", "")),
        updated_at=str(raw.get("updated_at", "")),
    )