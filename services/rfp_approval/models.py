from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field
from services.rfp_intake.models import now


class ApprovalRun(SQLModel, table=True):
    __tablename__ = "rfp_approval_run"
    ticket_id: str = Field(foreign_key="rfp_ticket.ticket_id", primary_key=True)
    started_at: datetime = Field(default_factory=now)


class Reviewer(SQLModel, table=True):
    __tablename__ = "rfp_reviewer"
    ticket_id: str = Field(foreign_key="rfp_ticket.ticket_id", primary_key=True)
    department_id: str = Field(primary_key=True)
    user_id: str = Field(index=True)


class ApprovalBranch(SQLModel, table=True):
    __tablename__ = "rfp_approval_branch"
    ticket_id: str = Field(foreign_key="rfp_ticket.ticket_id", primary_key=True)
    department_id: str = Field(primary_key=True)
    version: int
    revision_count: int = 0
    draft: dict = Field(sa_column=Column(JSON, nullable=False))
    evaluation: dict = Field(sa_column=Column(JSON, nullable=False))
    approval_status: str = "pending"
    response: dict | None = Field(default=None, sa_column=Column(JSON))
    approved_version: int | None = None
    approver: str | None = None
    approved_at: datetime | None = None
    token: str | None = None
    lease_until: datetime | None = None
    error: str | None = None


class ApprovalTrace(SQLModel, table=True):
    __tablename__ = "rfp_approval_trace"
    event_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    ticket_id: str = Field(foreign_key="rfp_ticket.ticket_id", index=True)
    department_id: str | None = None
    agent: str
    input: dict = Field(sa_column=Column(JSON, nullable=False))
    output: dict = Field(sa_column=Column(JSON, nullable=False))
    timestamp: datetime = Field(default_factory=now)


class ApprovalConflict(SQLModel, table=True):
    __tablename__ = "rfp_approval_conflict"
    ticket_id: str = Field(foreign_key="rfp_ticket.ticket_id", primary_key=True)
    trigger_id: str = Field(primary_key=True)
    department_ids: list = Field(sa_column=Column(JSON, nullable=False))
    versions: dict = Field(sa_column=Column(JSON, nullable=False))
    status: str = "pending"
    arbiter: str
    resolution: str
    actor: str | None = None


class FinalDocument(SQLModel, table=True):
    __tablename__ = "rfp_final_document"
    ticket_id: str = Field(foreign_key="rfp_ticket.ticket_id", primary_key=True)
    sections: dict = Field(sa_column=Column(JSON, nullable=False))
    currency: str
    content: str
    generated_at: datetime = Field(default_factory=now)


TABLES = [ApprovalRun, Reviewer, ApprovalBranch, ApprovalTrace, ApprovalConflict, FinalDocument]
