"""Typed, timeout-bounded inventory lookup tool for the LangGraph agent.

Replaces the unbounded inline SQL in ``graph.lookup_inventory()`` with a
bounded wrapper that enforces a configurable wall-clock timeout using a
module-level ``ThreadPoolExecutor`` (same pattern as ``incident.py``).

Usage::

    from services.agent.tools.inventory import lookup_inventory, InventoryLookupResponse

    result = lookup_inventory(timeout=5.0)
    # Returns list[InventoryLookupResponse] — raises InventoryToolError if >5 s.
"""

from __future__ import annotations

import concurrent.futures
import logging
from typing import TypedDict

logger = logging.getLogger(__name__)

# ── Default upper bound (seconds) ───────────────────────────────────────
INVENTORY_TIMEOUT = 5

# ── Reusable executor (module-level, no ``with`` — avoids shutdown deadlock)
_WRAPPER_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2)

# ======================================================================
# Typed field contracts
# ======================================================================


class InventoryLookupInput(TypedDict):
    """Input contract for the inventory lookup tool (reserved for future filtering)."""

    # No mandatory input fields currently — the tool returns all products.


class InventoryLookupResponse(TypedDict, total=False):
    """Output contract matching a single product/stock line.

    All fields are present for each product in the result list.
    """

    id: int
    name: str
    sku: str
    client_name: str
    category: str
    warehouse: str
    current_stock: int


# ======================================================================
# Tool error
# ======================================================================


class InventoryToolError(RuntimeError):
    """Raised when the inventory tool times out or fails unexpectedly."""


# ======================================================================
# Bounded lookup
# ======================================================================


def _do_lookup() -> list[dict]:
    """Execute the actual inventory query (called in the executor thread)."""
    from services.database import Session, engine
    from services.models import SKU, StockEntry, StockExit
    from sqlmodel import select, func

    result: list[dict] = []
    with Session(engine) as session:
        products = session.exec(select(SKU).order_by(SKU.id)).all()
        for product in products:
            inbound = session.exec(
                select(func.coalesce(func.sum(StockEntry.quantity), 0)).where(
                    StockEntry.sku_id == product.id,
                )
            ).one()
            outbound = session.exec(
                select(func.coalesce(func.sum(StockExit.quantity), 0)).where(
                    StockExit.sku_id == product.id,
                )
            ).one()
            result.append({
                "id": product.id,
                "name": product.name,
                "sku": product.sku,
                "client_name": product.client_name,
                "category": product.category,
                "warehouse": product.warehouse,
                "current_stock": int(inbound - outbound),
            })
    return result


def lookup_inventory(
    *,
    timeout: float | None = None,
) -> list[InventoryLookupResponse]:
    """Return all products with current stock levels.

    Parameters
    ----------
    timeout
        Optional per-call timeout in seconds.  Defaults to the module-level
        ``INVENTORY_TIMEOUT`` (5 s).

    Returns
    -------
    list[InventoryLookupResponse]
        One entry per product.  An empty list is returned on error or timeout
        (caller should check error state in agent context).

    Raises
    ------
    InventoryToolError
        If the call exceeds the timeout or fails unexpectedly.
    """
    effective_timeout = timeout if timeout is not None else INVENTORY_TIMEOUT

    future = _WRAPPER_EXECUTOR.submit(_do_lookup)
    try:
        raw_list = future.result(timeout=effective_timeout)
    except concurrent.futures.TimeoutError:
        logger.error(
            "Inventory lookup timed out after %s s",
            effective_timeout,
        )
        future.cancel()
        raise InventoryToolError(
            f"Inventory lookup timed out after {effective_timeout} s"
        )
    except Exception as exc:
        logger.error("Inventory lookup failed: %s", exc)
        raise InventoryToolError(
            f"Inventory lookup failed: {exc}"
        ) from exc

    return [
        InventoryLookupResponse(
            id=int(r.get("id", 0)),
            name=str(r.get("name", "")),
            sku=str(r.get("sku", "")),
            client_name=str(r.get("client_name", "")),
            category=str(r.get("category", "")),
            warehouse=str(r.get("warehouse", "")),
            current_stock=int(r.get("current_stock", 0)),
        )
        for r in raw_list
    ]