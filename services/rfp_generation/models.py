from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import SQLModel, Field
from services.rfp_intake.models import now


class ProposalRun(SQLModel, table=True):
    __tablename__ = "rfp_proposal_run"
    ticket_id: str = Field(foreign_key="rfp_ticket.ticket_id", primary_key=True)
    state: str = "queued"
    token: str | None = None
    lease_until: datetime | None = None
    runs: int = 0
    progress: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    handoff: dict | None = Field(default=None, sa_column=Column(JSON))
    error_message: str | None = None
    updated_at: datetime = Field(default_factory=now)


class ProposalAttempt(SQLModel, table=True):
    __tablename__ = "rfp_proposal_attempt"
    __table_args__ = (UniqueConstraint("ticket_id", "department_id", "version", name="rfp_proposal_version"),)
    attempt_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    ticket_id: str = Field(foreign_key="rfp_ticket.ticket_id", index=True)
    department_id: str
    version: int
    draft: dict = Field(sa_column=Column(JSON, nullable=False))
    evaluation: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now)
