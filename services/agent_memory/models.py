"""Strict schemas and conservative content boundary for persistent memory."""
from __future__ import annotations
import hashlib
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class Scope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    company: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    actor: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.@-]+$")
    conversation: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")

class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["carrier_rule", "recurring_incident", "report_preference"]
    entity: str = Field(min_length=2, max_length=80)
    country: Literal["US", "ES"]
    fact: str = Field(min_length=10, max_length=500)
    reason: str = Field(min_length=10, max_length=300)

class Evaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=10000)
    memory_proposal: Candidate | None = None

class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_id: str
    version: int = Field(ge=1)
    label: Literal["approve", "reject", "edit", "unrelated", "uncertain"]
    confidence: float = Field(ge=0, le=1)
    remaining_question: str = Field(default="", max_length=4000)
    edited_proposal: Candidate | None = None

# Defense in depth. The model must also apply semantic restrictions before extraction.
# Refuse suspicious content rather than retaining a partially redacted fact.
_FORBIDDEN = re.compile(
    r"address|street|avenue|boulevard|postcode|postal.code|zip.code|latitude|longitude|coordinates|"
    r"\b(unit|suite|apartment|building|dock|door|aisle|floor|piso|puerta|portal)\s*[#:]?\s*\d+|"
    r"\b\d{5}(?:-\d{4})?\b|"
    r"warehouse.{0,40}(route|layout|entrance|door|aisle|location)|"
    r"(route|layout|entrance|door|aisle).{0,40}warehouse|"
    r"\b\d{1,6}\s+[A-Za-zÀ-ÿ ]{2,40}\s+(st|rd|ave|road|lane|calle|carrer)\b|"
    r"\b(calle|carrer|avenida|direccion|dirección|domicilio)\b|"
    r"-?\d{1,3}\.\d{3,}\s*[,;]\s*-?\d{1,3}\.\d{3,}|"
    r"contract|negotiat|commercial terms|pricing agreement|tracking|parcel.?id|package.?id|"
    r"ignore.{0,30}(instruction|rule|policy)|system.prompt|api.key|password|secret|"
    r"disable.{0,30}(auth|guard|security)|always obey|you must|override|exfiltrat|"
    r"return window|refund policy|security policy|access.token|https?://",
    re.I,
)

def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

def validate_candidate(candidate: Candidate, source: str | None = None) -> Candidate:
    fields = ' '.join((candidate.entity, candidate.fact, candidate.reason))
    if _FORBIDDEN.search(fields) or (source is not None and _FORBIDDEN.search(source)):
        raise ValueError("This interaction is outside the permitted operational memory categories.")
    if candidate.kind == "report_preference" and not re.search(r"report|metric|format|breakdown|monthly|informe", candidate.fact, re.I):
        raise ValueError("Report preferences must describe recurring reporting needs.")
    if candidate.kind == "carrier_rule" and not re.search(r"carrier|coverage|cover|route|SEUR|DHL|UPS|FedEx|transportista", candidate.fact, re.I):
        raise ValueError("Carrier memories must describe carrier coverage or assignment.")
    if candidate.kind == "recurring_incident" and not re.search(r"recurr|repeat|multiple|several|third|this week|strike|recurrent", candidate.fact, re.I):
        raise ValueError("Isolated incidents are not memorable.")
    return candidate

def fact_key(candidate: Candidate) -> str:
    entity = re.sub(r"\s+", " ", candidate.entity.strip().casefold())
    return f"{candidate.kind}:{candidate.country}:{entity}"
