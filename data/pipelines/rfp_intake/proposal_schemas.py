"""Versioned Part 2 contracts. Model outputs are data, never executable instructions."""

from typing import Literal
from pydantic import Field
from .schemas import Strict, Department
from .approval_rules import Commitments

MAX_ATTEMPTS = 3


class DiscountTier(Strict):
    volume_basis: str = Field(min_length=3, max_length=250)
    discount_percent: float | None = Field(default=None, ge=0, le=100)
    approval_required: bool


class ProposalDraft(Strict):
    department_id: Department
    content: str = Field(min_length=80, max_length=12000)
    currency: Literal["USD", "EUR"] | None
    on_time_sla_percent: float | None = Field(ge=0, le=100)
    returns_turnaround_hours: float | None = Field(ge=0)
    volume_discount_tiers: list[DiscountTier] = Field(max_length=8)
    source_ids: list[str] = Field(min_length=1, max_length=12)
    open_questions: list[str] = Field(default_factory=list, max_length=15)
    commitments: Commitments | None = None


class RelevanceResult(Strict):
    missing_aspects: list[str] = Field(max_length=15)
    unsupported_claims: list[str] = Field(default_factory=list, max_length=15)


class ComplianceFinding(Strict):
    rule_id: str = Field(min_length=2, max_length=60)
    violation: str = Field(min_length=5, max_length=700)


class ComplianceReview(Strict):
    violations: list[ComplianceFinding] = Field(max_length=20)


class EvaluationResult(Strict):
    section_id: str
    department_id: Department
    draft_version: int = Field(ge=1, le=MAX_ATTEMPTS)
    readability: dict
    relevance: dict
    compliance: dict
    overall_pass: bool
    feedback_for_generator: str
