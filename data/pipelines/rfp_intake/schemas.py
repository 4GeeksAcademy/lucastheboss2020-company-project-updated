"""Validated contracts for TrackFlow RFP intake agents and the Part 2 handoff."""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Department = Literal["warehouse", "lastmile", "reverse"]
OWNERS = {"warehouse": "Ana Whitfield", "lastmile": "Carlos Vega", "reverse": "Sofía Ramos"}
LABELS = {
    "warehouse": "Warehouse Operations",
    "lastmile": "Last Mile and Carrier Management",
    "reverse": "Reverse Logistics",
}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Classification(Strict):
    accepted: bool
    reason: str = Field(min_length=5, max_length=600)
    evidence: list[str] = Field(min_length=1, max_length=5)


class Metadata(Strict):
    client_name: str | None = Field(default=None, max_length=160)
    client_country: Literal["US", "ES"] | None = None
    services_requested: list[Department] = Field(max_length=3)
    monthly_volume: str | None = Field(default=None, max_length=200)
    deadline: str | None = Field(default=None, max_length=200)
    budget_range: str | None = Field(default=None, max_length=300)
    evidence: dict[str, list[str]] = Field(default_factory=dict)


class Assignment(Strict):
    department_id: Department
    extracts: list[str] = Field(min_length=1, max_length=12)


class Plan(Strict):
    metadata: Metadata
    assignments: list[Assignment] = Field(min_length=1, max_length=3)
    open_questions: list[str] = Field(default_factory=list, max_length=12)


class Aspect(Strict):
    requirement: str = Field(min_length=3, max_length=600)
    evidence: str = Field(min_length=5, max_length=1500)


class WorkerResult(Strict):
    department_id: Department
    key_aspects: list[Aspect] = Field(min_length=1, max_length=12)
    open_questions: list[str] = Field(default_factory=list, max_length=12)


class Synthesis(Strict):
    summary: str = Field(min_length=10, max_length=3000)
    open_questions: list[str] = Field(default_factory=list, max_length=18)
    conflicts: list[str] = Field(default_factory=list, max_length=12)
