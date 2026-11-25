"""Deterministic structured contradictions. Never compare incompatible units."""
import re
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

OWNERS = {"warehouse": "Ana Whitfield", "lastmile": "Carlos Vega", "reverse": "Sofía Ramos", "arbiter": "Miguel Torres"}
MAX_REVISIONS = 3


class Quantity(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    value: float = Field(gt=0)
    unit: str = Field(pattern=r"^(orders|pallets|skus|cubic_meters)$")
    period: str = Field(pattern=r"^(month|day|total)$")
    evidence: str = Field(min_length=8, max_length=2000)


class Commitments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capacity: Quantity | None = None
    volume: Quantity | None = None
    customer_total_cost: "CustomerCost | None" = None


class CustomerCost(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    amount: float = Field(ge=0)
    currency: str = Field(pattern=r"^(USD|EUR)$")
    period: str = Field(pattern=r"^(month|day|total)$")
    evidence: str = Field(min_length=8, max_length=2000)


Commitments.model_rebuild()


def capacity_revision_valid(previous, revised, capacity):
    old = (previous.get("commitments") or {})
    new = (revised.get("commitments") or {})
    volume = new.get("volume")
    if not old.get("volume") or not volume or not capacity or (volume["unit"], volume["period"]) != (capacity["unit"], capacity["period"]) or volume["value"] > capacity["value"]:
        return False
    # Only compare supported totals for the same billing period. Never invent
    # a rate, conversion or fixed/variable cost split when no total was quoted.
    quoted = old.get("customer_total_cost")
    if quoted is not None:
        corrected = new.get("customer_total_cost")
        if not corrected or (quoted["currency"], quoted["period"]) != (corrected["currency"], corrected["period"]):
            return False
        if corrected["amount"] > quoted["amount"] or (quoted["amount"] > 0 and corrected["amount"] == quoted["amount"]):
            return False
    return True


def quantity_grounded(quantity, source):
    """Bind magnitude, unit and time basis to a real quote, not merely an arbitrary sentence."""
    quote = quantity.evidence.casefold()
    canonical = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", quote)
    values = {Decimal(n) for n in re.findall(r"(?<![\w.])\d+(?:\.\d+)?", canonical)}
    units = {"orders": r"orders?|shipments?", "pallets": r"pallets?", "skus": r"skus?",
             "cubic_meters": r"cubic\s*met(?:er|re)s?|m[³3]"}
    periods = {"month": r"monthly|months?", "day": r"daily|days?", "total": r"total|overall"}
    return (quantity.evidence in source and Decimal(str(quantity.value)) in values
            and bool(re.search(units[quantity.unit], quote))
            and bool(re.search(periods[quantity.period], quote)))


def conflicts(branches, country):
    expected = {"US": "USD", "ES": "EUR"}.get(country)
    out = []
    bad = [b.department_id for b in branches if b.draft.get("currency") != expected or expected is None]
    if bad:
        out.append(dict(trigger_id="currency-mismatch", department_ids=bad, arbiter="arbiter",
                        resolution=f"Revise offending quotations to {expected or 'a verified country currency'}; never invent exchange rates."))
    bad = [b.department_id for b in branches if (b.draft.get("returns_turnaround_hours") is not None
               and b.draft["returns_turnaround_hours"] < 48) or re.search(
                   r"returns?[^.\n]{0,70}(?:24\s*hours?|one\s*day|same.day)", b.draft.get("content", ""), re.I)]
    if bad:
        out.append(dict(trigger_id="returns-sla-breach", department_ids=bad,
                        arbiter="reverse" if set(bad) == {"reverse"} else "arbiter",
                        resolution="Force request_changes on every affected section; returns must take at least 48 hours."))
    by_dept = {b.department_id: b for b in branches}
    if {"warehouse", "lastmile"}.issubset(by_dept):
        cap = (by_dept["warehouse"].draft.get("commitments") or {}).get("capacity")
        vol = (by_dept["lastmile"].draft.get("commitments") or {}).get("volume")
        if cap and vol:
            cap, vol = Quantity.model_validate(cap), Quantity.model_validate(vol)
            if (cap.unit, cap.period) == (vol.unit, vol.period) and cap.value < vol.value:
                out.append(dict(trigger_id="volume-vs-capacity", department_ids=["lastmile"], arbiter="arbiter",
                                resolution=f"Cap lastmile volume at {cap.value:g} {cap.unit}/{cap.period}; revise quoted volume and cost downward without inventing prices."))
    return out
