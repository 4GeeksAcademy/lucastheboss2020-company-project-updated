"""Durable per-section checkpoints. Every write is fenced by the active run token."""

from datetime import timedelta
from uuid import uuid4
from sqlalchemy import update, or_
from sqlmodel import Session, select
from services.rfp_intake.models import Ticket, DepartmentSection, now
from .models import ProposalRun, ProposalAttempt


class SupersededRun(RuntimeError):
    pass


class ProposalStore:
    def __init__(self, engine):
        self.engine = engine

    def start(self, ticket_id, owner, retry=False):
        with Session(self.engine) as db:
            ticket = db.exec(select(Ticket).where(Ticket.ticket_id == ticket_id, Ticket.owner_id == owner)).first()
            if not ticket:
                return "not_found"
            # Match checkpoints/finalization: lock run before ticket to avoid retry/worker deadlocks.
            run = db.exec(select(ProposalRun).where(ProposalRun.ticket_id == ticket_id).with_for_update()).first()
            ticket = db.exec(select(Ticket).where(Ticket.ticket_id == ticket_id).with_for_update()).one()
            db.refresh(ticket)
            if not retry:
                # Compare-and-set is also safe on SQLite; PostgreSQL additionally locks the row.
                if (
                    run
                    or not ticket.handoff
                    or not ticket.handoff.get("ready_for_part2")
                    or ticket.handoff.get("schema_version") != 1
                    or ticket.handoff.get("next_step") != "proposal_generation"
                    or not ticket.handoff.get("sections")
                ):
                    return "conflict"
                result = db.exec(
                    update(Ticket)
                    .where(Ticket.ticket_id == ticket_id, Ticket.status == "intake_complete")
                    .values(
                        status="drafting",
                        processing_state="queued",
                        stage="Proposal generation queued",
                        updated_at=now(),
                    )
                )
                if result.rowcount != 1:
                    return "conflict"
                db.add(ProposalRun(ticket_id=ticket_id))
            else:
                stale = run and run.state in {"queued", "running"} and (now() - run.updated_at).total_seconds() > 900
                if (
                    not run
                    or run.runs >= 6
                    or ticket.status not in {"drafting", "under_evaluation"}
                    or (run.state != "failed" and not stale)
                ):
                    return "conflict"
                run.state, run.token, run.lease_until, run.error_message = "queued", None, None, None
                run.updated_at = now()
                ticket.processing_state, ticket.stage = "queued", "Proposal retry queued"
                ticket.updated_at = now()
                db.add(run)
                db.add(ticket)
            db.commit()
            return "accepted"

    def claim(self, ticket_id):
        token = str(uuid4())
        with Session(self.engine) as db:
            ticket = db.get(Ticket, ticket_id)
            if not ticket or ticket.status not in {"drafting", "under_evaluation"}:
                return None
            sections = db.exec(select(DepartmentSection).where(DepartmentSection.ticket_id == ticket_id)).all()
            handoff = ticket.handoff
            wanted = [s["department_id"] for s in handoff["sections"]]
            if not wanted or len(wanted) != len(set(wanted)) or set(wanted) != {s.department_id for s in sections}:
                raise ValueError("Incomplete Part 1 handoff")
            contexts = []
            for section in sections:
                source = next(s for s in handoff["sections"] if s["department_id"] == section.department_id)
                contexts.append(
                    {
                        "section_id": section.section_id,
                        "department_id": section.department_id,
                        "metadata": handoff["metadata"],
                        "key_aspects": source["key_aspects"],
                        "open_questions": source.get("open_questions", []),
                    }
                )
            result = db.exec(
                update(ProposalRun)
                .where(
                    ProposalRun.ticket_id == ticket_id,
                    ProposalRun.state == "queued",
                    ProposalRun.runs < 6,
                    or_(ProposalRun.lease_until == None, ProposalRun.lease_until < now()),
                )
                .values(
                    state="running",
                    token=token,
                    lease_until=now() + timedelta(minutes=12),
                    runs=ProposalRun.runs + 1,
                    updated_at=now(),
                    error_message=None,
                )
            )
            db.commit()
            if result.rowcount != 1:
                return None
            return token, contexts

    def latest(self, ticket_id, department_id):
        with Session(self.engine) as db:
            row = db.exec(
                select(ProposalAttempt)
                .where(ProposalAttempt.ticket_id == ticket_id, ProposalAttempt.department_id == department_id)
                .order_by(ProposalAttempt.version.desc())
            ).first()
            return {"version": row.version, "draft": row.draft, "evaluation": row.evaluation} if row else None

    def checkpoint(self, ticket_id, token, department, phase, version, draft=None, evaluation=None):
        with Session(self.engine) as db:
            run = db.exec(select(ProposalRun).where(ProposalRun.ticket_id == ticket_id).with_for_update()).first()
            if not run or run.state != "running" or run.token != token:
                raise SupersededRun("Proposal execution was superseded")
            section = db.exec(
                select(DepartmentSection).where(
                    DepartmentSection.ticket_id == ticket_id, DepartmentSection.department_id == department
                )
            ).one()
            if draft is not None:
                if not 1 <= version <= 3 or draft["department_id"] != department:
                    raise ValueError("Invalid draft checkpoint")
                row = db.exec(
                    select(ProposalAttempt).where(
                        ProposalAttempt.ticket_id == ticket_id,
                        ProposalAttempt.department_id == department,
                        ProposalAttempt.version == version,
                    )
                ).first()
                if row is None:
                    row = ProposalAttempt(ticket_id=ticket_id, department_id=department, version=version, draft=draft)
                    db.add(row)
                elif row.draft != draft:
                    raise ValueError("Cannot overwrite an existing draft version")
                section.draft_content = draft["content"]
                if evaluation is not None:
                    if evaluation["department_id"] != department or evaluation["draft_version"] != version:
                        raise ValueError("Evaluation belongs to a different draft")
                    row.evaluation = evaluation
                    section.evaluation_results = evaluation
                    db.add(row)
                else:
                    section.evaluation_results = None
                db.add(section)
            run.progress = dict(run.progress, **{department: {"phase": phase, "attempt": version, "max_attempts": 3}})
            run.updated_at = now()
            run.lease_until = now() + timedelta(minutes=12)
            ticket = db.get(Ticket, ticket_id)
            ticket.status = (
                "under_evaluation" if any(p["phase"] != "drafting" for p in run.progress.values()) else "drafting"
            )
            ticket.processing_state, ticket.stage, ticket.updated_at = (
                "running",
                "Generating and checking proposal sections",
                now(),
            )
            db.add(ticket)
            db.add(run)
            db.commit()

    def fail(self, ticket_id, token=None):
        with Session(self.engine) as db:
            query = update(ProposalRun).where(ProposalRun.ticket_id == ticket_id)
            query = (
                query.where(ProposalRun.token == token, ProposalRun.state == "running")
                if token
                else query.where(ProposalRun.state == "queued")
            )
            result = db.exec(
                query.values(
                    state="failed",
                    token=None,
                    lease_until=None,
                    updated_at=now(),
                    error_message="Proposal processing was interrupted. Saved drafts are retained; retry to continue.",
                )
            )
            if result.rowcount:
                t = db.get(Ticket, ticket_id)
                t.processing_state, t.stage, t.updated_at = "failed", "Proposal generation needs attention", now()
                db.add(t)
            db.commit()

    def finish(self, ticket_id, token, results):
        with Session(self.engine) as db:
            run = db.exec(select(ProposalRun).where(ProposalRun.ticket_id == ticket_id).with_for_update()).first()
            if not run or run.state != "running" or run.token != token:
                raise SupersededRun("Proposal execution was superseded")
            t = db.get(Ticket, ticket_id)
            expected = {s["department_id"] for s in t.handoff["sections"]}
            if len(results) != len(expected) or {s["department_id"] for s in results} != expected:
                raise ValueError("Incomplete proposal handoff")
            review = any(not s["evaluation"]["overall_pass"] for s in results)
            run.handoff = {
                "schema_version": 1,
                "ticket_id": ticket_id,
                "ready_for_part3": True,
                "currency": t.handoff["metadata"].get("currency"),
                "sections": sorted(results, key=lambda s: s["department_id"]),
            }
            run.state, run.token, run.lease_until, run.updated_at = "complete", None, None, now()
            t.status = "needs_human_review" if review else "under_evaluation"
            t.processing_state = "complete"
            t.stage = "Drafts retained for human review" if review else "Automated checks complete; ready for Part 3"
            t.updated_at = now()
            db.add(run)
            db.add(t)
            db.commit()

    @staticmethod
    def serialize(db, ticket_id):
        run = db.get(ProposalRun, ticket_id)
        if not run:
            return None
        stale = run.state in {"running", "queued"} and (now() - run.updated_at).total_seconds() > 900
        history = db.exec(
            select(ProposalAttempt)
            .where(ProposalAttempt.ticket_id == ticket_id)
            .order_by(ProposalAttempt.department_id, ProposalAttempt.version)
        ).all()
        return {
            "state": run.state,
            "progress": run.progress,
            "handoff": run.handoff,
            "error_message": run.error_message,
            "stalled": stale,
            "runs": run.runs,
            "can_retry": run.runs < 6 and (run.state == "failed" or stale),
            "attempts": [
                {"department_id": r.department_id, "version": r.version, "draft": r.draft, "evaluation": r.evaluation}
                for r in history
            ],
        }
