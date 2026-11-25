"""Additive SQLModel tables. PostgreSQL is the deployed source of truth."""

from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column, JSON, CheckConstraint, UniqueConstraint
from sqlmodel import SQLModel, Field


def now():
    return datetime.now(timezone.utc)


class Ticket(SQLModel, table=True):
    __tablename__ = "rfp_ticket"
    __table_args__ = (
        CheckConstraint(
            "status IN ('analyzing','discarded','intake_complete','drafting','under_evaluation','needs_human_review','waiting_for_approval','done')",
            name="rfp_ticket_status",
        ),
    )
    ticket_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    owner_id: str = Field(index=True, max_length=100)
    rfp_id: str = Field(default_factory=lambda: str(uuid4()), unique=True)
    original_filename: str = Field(max_length=180)
    raw_pdf_path: str
    sha256: str = Field(max_length=64)
    status: str = Field(default="analyzing", index=True)
    processing_state: str = "queued"
    stage: str = "Upload accepted"
    error_code: str | None = None
    error_message: str | None = None
    classification_reason: str | None = None
    classification_evidence: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    handoff: dict | None = Field(default=None, sa_column=Column(JSON))
    attempts: int = 0
    run_token: str | None = None
    lease_until: datetime | None = None
    created_at: datetime = Field(default_factory=now, index=True)
    updated_at: datetime = Field(default_factory=now)


class RFPMetadata(SQLModel, table=True):
    __tablename__ = "rfp_metadata"
    ticket_id: str = Field(foreign_key="rfp_ticket.ticket_id", primary_key=True)
    client_name: str | None = None
    client_country: str | None = None
    currency: str | None = None
    services_requested: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    monthly_volume: str | None = None
    deadline: str | None = None
    budget_range: str | None = None
    departments_needed: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    evidence: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    readability_metrics: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class DepartmentSection(SQLModel, table=True):
    __tablename__ = "rfp_department_section"
    __table_args__ = (
        CheckConstraint("department_id IN ('warehouse','lastmile','reverse')", name="rfp_department_id"),
        UniqueConstraint("ticket_id", "department_id", name="rfp_unique_section"),
    )
    section_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    ticket_id: str = Field(foreign_key="rfp_ticket.ticket_id", index=True)
    department_id: str
    owner: str
    key_aspects: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    open_questions: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    draft_content: str | None = None
    evaluation_results: dict | None = Field(default=None, sa_column=Column(JSON))
    approval_status: str = "not_started"
    approver: str | None = None
    approved_at: datetime | None = None


def create_tables(engine):
    from services.rfp_generation.models import ProposalRun, ProposalAttempt
    from services.rfp_approval.models import TABLES
    SQLModel.metadata.create_all(engine, tables=[Ticket.__table__, RFPMetadata.__table__, DepartmentSection.__table__,
        ProposalRun.__table__, ProposalAttempt.__table__, *[t.__table__ for t in TABLES]])
