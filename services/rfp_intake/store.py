"""Transactional ticket lifecycle with ownership, leases and idempotent results."""

from datetime import timedelta
from uuid import uuid4
from sqlalchemy import update, or_
from sqlmodel import Session, select
from .models import Ticket, RFPMetadata, DepartmentSection, now


class Store:
    def __init__(self, engine):
        self.engine = engine

    def create(self, ticket):
        with Session(self.engine) as db:
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            return ticket

    def owned(self, ticket_id, owner):
        with Session(self.engine) as db:
            return db.exec(select(Ticket).where(Ticket.ticket_id == ticket_id, Ticket.owner_id == owner)).first()

    def list(self, owner, offset=0, limit=30):
        with Session(self.engine) as db:
            rows = db.exec(
                select(Ticket)
                .where(Ticket.owner_id == owner)
                .order_by(Ticket.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).all()
            return [self.serialize(db, t) for t in rows]

    def details(self, ticket_id, owner):
        with Session(self.engine) as db:
            t = db.exec(select(Ticket).where(Ticket.ticket_id == ticket_id, Ticket.owner_id == owner)).first()
            return self.serialize(db, t) if t else None

    def serialize(self, db, t):
        data = t.model_dump(exclude={"owner_id", "raw_pdf_path", "run_token", "lease_until", "sha256"})
        metadata = db.get(RFPMetadata, t.ticket_id)
        data["metadata"] = metadata.model_dump(exclude={"ticket_id"}) if metadata else None
        data["sections"] = [
            s.model_dump(exclude={"section_id", "ticket_id"})
            for s in db.exec(select(DepartmentSection).where(DepartmentSection.ticket_id == t.ticket_id)).all()
        ]
        stale = t.processing_state in {"running", "retrying", "queued"} and (now() - t.updated_at).total_seconds() > 900
        data["stalled"] = stale
        data["can_retry"] = t.status == "analyzing" and t.attempts < 6 and (t.processing_state == "failed" or stale)
        return data

    def claim(self, ticket_id):
        token = str(uuid4())
        current = now()
        with Session(self.engine) as db:
            result = db.exec(
                update(Ticket)
                .where(
                    Ticket.ticket_id == ticket_id,
                    Ticket.status == "analyzing",
                    Ticket.processing_state.in_(["queued", "retrying"]),
                    Ticket.attempts < 6,
                    or_(Ticket.lease_until == None, Ticket.lease_until < current),
                )
                .values(
                    processing_state="running",
                    run_token=token,
                    lease_until=current + timedelta(minutes=12),
                    attempts=Ticket.attempts + 1,
                    updated_at=current,
                    error_code=None,
                    error_message=None,
                )
            )
            db.commit()
            if result.rowcount != 1:
                return None
            t = db.get(Ticket, ticket_id)
            return t, token

    def progress(self, ticket_id, token, stage):
        with Session(self.engine) as db:
            db.exec(
                update(Ticket)
                .where(Ticket.ticket_id == ticket_id, Ticket.run_token == token, Ticket.processing_state == "running")
                .values(stage=stage, updated_at=now())
            )
            db.commit()

    def fail(self, ticket_id, token, code, message, retrying=False):
        with Session(self.engine) as db:
            query = update(Ticket).where(Ticket.ticket_id == ticket_id, Ticket.status == "analyzing")
            if token:
                query = query.where(Ticket.run_token == token)
            else:
                query = query.where(Ticket.processing_state == "queued")
            db.exec(
                query.values(
                    processing_state="retrying" if retrying else "failed",
                    stage="Retry scheduled" if retrying else "Processing needs attention",
                    error_code=code,
                    error_message=message,
                    run_token=None,
                    lease_until=None,
                    updated_at=now(),
                )
            )
            db.commit()

    def finish(self, ticket_id, token, state):
        with Session(self.engine) as db:
            t = db.exec(select(Ticket).where(Ticket.ticket_id == ticket_id).with_for_update()).first()
            if not t or t.run_token != token or t.processing_state != "running":
                return False
            c = state["classification"]
            t.classification_reason = c["reason"]
            t.classification_evidence = c["evidence"]
            metrics = state["metrics"]
            if not c["accepted"]:
                t.status = "discarded"
                t.processing_state = "discarded"
                t.stage = "Not a client RFP"
                db.add(RFPMetadata(ticket_id=ticket_id, readability_metrics=metrics))
            else:
                result = dict(state["result"], ticket_id=ticket_id, rfp_id=t.rfp_id)
                m = result["metadata"]
                db.add(
                    RFPMetadata(
                        ticket_id=ticket_id,
                        **m,
                        departments_needed=m["services_requested"],
                        readability_metrics=metrics,
                    )
                )
                for section in result["sections"]:
                    db.add(
                        DepartmentSection(
                            ticket_id=ticket_id,
                            department_id=section["department_id"],
                            owner=section["owner"],
                            key_aspects=section["key_aspects"],
                            open_questions=section["open_questions"],
                        )
                    )
                t.handoff = result
                t.status = "intake_complete"
                t.processing_state = "complete"
                t.stage = "Ready for Sales review"
            t.run_token = None
            t.lease_until = None
            t.updated_at = now()
            t.error_code = None
            t.error_message = None
            db.add(t)
            db.commit()
            return True

    def prepare_retry(self, ticket_id, owner):
        current = now()
        with Session(self.engine) as db:
            t = db.exec(
                select(Ticket).where(Ticket.ticket_id == ticket_id, Ticket.owner_id == owner).with_for_update()
            ).first()
            if not t or t.status != "analyzing" or t.attempts >= 6:
                return False
            stale = (current - t.updated_at).total_seconds() > 900
            if t.processing_state != "failed" and not stale:
                return False
            t.processing_state = "queued"
            t.run_token = None
            t.lease_until = None
            t.error_code = None
            t.error_message = None
            t.stage = "Retry accepted"
            t.updated_at = current
            db.add(t)
            db.commit()
            return True
