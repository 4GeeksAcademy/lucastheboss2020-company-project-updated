"""Transactional business records; graph checkpoints remain separate durable execution state."""
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import update, or_
from sqlmodel import Session, select
from services.rfp_intake.models import Ticket, RFPMetadata, DepartmentSection, now
from services.rfp_generation.models import ProposalRun
from .models import ApprovalRun, ApprovalBranch, ApprovalTrace, ApprovalConflict, Reviewer, FinalDocument
from data.pipelines.rfp_intake.approval_rules import OWNERS, MAX_REVISIONS, conflicts


class ApprovalError(ValueError):
    def __init__(self, message, code=409):
        super().__init__(message)
        self.code = code


class ApprovalStore:
    def __init__(self, engine):
        self.engine = engine

    @staticmethod
    def trace(db, ticket_id, department, agent, input, output):
        db.add(ApprovalTrace(ticket_id=ticket_id, department_id=department, agent=agent, input=input, output=output))

    @staticmethod
    def access(db, ticket_id, actor, creator=False):
        t = db.get(Ticket, ticket_id)
        assigned = db.exec(select(Reviewer).where(Reviewer.ticket_id == ticket_id, Reviewer.user_id == actor)).first()
        if not t or (t.owner_id != actor and (creator or not assigned)):
            raise ApprovalError("Ticket not found.", 404)
        return t

    @staticmethod
    def lock_ticket(db, ticket_id):
        return db.exec(select(Ticket).where(Ticket.ticket_id == ticket_id).with_for_update().execution_options(populate_existing=True)).one()

    def assign(self, ticket_id, actor, department, user_id):
        if department not in OWNERS:
            raise ApprovalError("Unknown department.", 422)
        with Session(self.engine) as db:
            self.access(db, ticket_id, actor, creator=True)
            self.lock_ticket(db, ticket_id)
            existing = db.get(Reviewer, (ticket_id, department))
            if existing and existing.user_id != user_id and db.get(ApprovalRun, ticket_id):
                raise ApprovalError("Reviewers cannot be replaced after approval starts.")
            db.merge(Reviewer(ticket_id=ticket_id, department_id=department, user_id=user_id))
            self.trace(db, ticket_id, department, "assign_reviewer", {"actor": actor}, {"user_id": user_id, "owner": OWNERS[department]})
            db.commit()

    def start(self, ticket_id, actor):
        with Session(self.engine) as db:
            t = self.access(db, ticket_id, actor, creator=True)
            t = self.lock_ticket(db, ticket_id)
            if db.get(ApprovalRun, ticket_id):
                return
            p = db.get(ProposalRun, ticket_id)
            if t.status not in {"under_evaluation", "needs_human_review"} or not p or p.state != "complete" or not (p.handoff or {}).get("ready_for_part3"):
                raise ApprovalError("A completed Part 2 handoff is required.")
            sections = p.handoff.get("sections", [])
            actual = db.exec(select(DepartmentSection).where(DepartmentSection.ticket_id == ticket_id)).all()
            if not sections or {s["department_id"] for s in sections} != {s.department_id for s in actual}:
                raise ApprovalError("The proposal handoff does not match the active departments.")
            for s in sections:
                if not db.get(Reviewer, (ticket_id, s["department_id"])):
                    raise ApprovalError("Assign an existing user to each named department owner first.")
                db.add(ApprovalBranch(ticket_id=ticket_id, department_id=s["department_id"],
                                      version=s["attempts"], draft=s["draft"], evaluation=s["evaluation"]))
            db.add(ApprovalRun(ticket_id=ticket_id))
            t.status, t.stage, t.processing_state = "waiting_for_approval", "Department approvals pending", "complete"
            t.updated_at = now()
            db.add(t)
            self.trace(db, ticket_id, None, "approval_start", {"departments": [s["department_id"] for s in sections]}, {"status": t.status})
            db.commit()
        self.arbitrate(ticket_id)

    def branches(self, ticket_id):
        with Session(self.engine) as db:
            return list(db.exec(select(ApprovalBranch).where(ApprovalBranch.ticket_id == ticket_id)).all())

    def branch(self, ticket_id, department):
        with Session(self.engine) as db:
            return db.get(ApprovalBranch, (ticket_id, department))

    def arbitrate(self, ticket_id):
        with Session(self.engine) as db:
            t = db.exec(select(Ticket).where(Ticket.ticket_id == ticket_id).with_for_update()).one()
            rows = list(db.exec(select(ApprovalBranch).where(ApprovalBranch.ticket_id == ticket_id)).all())
            meta = db.get(RFPMetadata, ticket_id)
            findings = conflicts(rows, meta.client_country if meta else None)
            active = {x["trigger_id"] for x in findings}
            for previous in db.exec(select(ApprovalConflict).where(ApprovalConflict.ticket_id == ticket_id)).all():
                if previous.trigger_id not in active:
                    previous.status = "resolved"
                    db.add(previous)
            for f in findings:
                dependencies = set(f["department_ids"]) | ({"warehouse"} if f["trigger_id"] == "volume-vs-capacity" else set())
                versions = {b.department_id: b.version for b in rows if b.department_id in dependencies}
                old = db.get(ApprovalConflict, (ticket_id, f["trigger_id"]))
                if old and old.versions == versions and old.status in {"request_changes", "rejected"}:
                    continue
                row = ApprovalConflict(ticket_id=ticket_id, **f, versions=versions)
                db.merge(row)
                for b in rows:
                    if b.department_id in f["department_ids"] and b.approval_status == "approved":
                        b.approval_status, b.approved_version, b.approver, b.approved_at = "pending", None, None, None
                        db.add(b)
                        self.sync_section(db, b)
            self.trace(db, ticket_id, None, "arbitration", {"versions": {b.department_id: b.version for b in rows}}, {"conflicts": findings})
            db.commit()
            return findings

    @staticmethod
    def sync_section(db, b):
        section = db.exec(select(DepartmentSection).where(DepartmentSection.ticket_id == b.ticket_id, DepartmentSection.department_id == b.department_id)).one()
        section.draft_content, section.evaluation_results = b.draft["content"], b.evaluation
        section.approval_status, section.approver, section.approved_at = b.approval_status, b.approver, b.approved_at
        db.add(section)

    def respond(self, ticket_id, department, actor, decision, version, feedback=""):
        if decision not in {"approve", "reject", "request_changes"} or (decision != "approve" and not feedback.strip()):
            raise ApprovalError("A valid decision and feedback for changes or rejection are required.", 422)
        with Session(self.engine) as db:
            self.access(db, ticket_id, actor)
            t = self.lock_ticket(db, ticket_id)
            if t.status == "done":
                raise ApprovalError("The approved final document is immutable.")
            b = db.exec(select(ApprovalBranch).where(ApprovalBranch.ticket_id == ticket_id, ApprovalBranch.department_id == department).with_for_update()).first()
            reviewer = db.get(Reviewer, (ticket_id, department))
            if not b or not reviewer or reviewer.user_id != actor:
                raise ApprovalError("Only the assigned department owner can decide.", 403)
            if version != b.version or b.approval_status != "pending" or b.response:
                raise ApprovalError("This draft changed or already has a decision; refresh it.")
            blocked = db.exec(select(ApprovalConflict).where(ApprovalConflict.ticket_id == ticket_id, ApprovalConflict.status != "resolved")).all()
            if decision == "approve" and (not b.evaluation.get("overall_pass") or any(department in c.department_ids for c in blocked)):
                raise ApprovalError("Resolve evaluation failures and arbitration before approval.")
            if decision == "request_changes" and any(department in c.department_ids and c.status == "pending" for c in blocked):
                raise ApprovalError("The fixed arbiter must record this conflict's resolution through the arbitration controls first.")
            if decision == "request_changes" and b.revision_count >= MAX_REVISIONS:
                raise ApprovalError("The three-round human revision limit has been reached.")
            b.response = {"decision": decision, "version": version, "feedback": feedback, "actor": actor, "request_id": str(uuid4())}
            db.add(b)
            self.trace(db, ticket_id, department, "human_response", {"actor": actor, "version": version}, dict(b.response))
            db.commit()

    def resolve(self, ticket_id, actor, trigger_id, decision, feedback):
        if decision not in {"request_changes", "reject"} or not feedback.strip():
            raise ApprovalError("Arbitration requires request_changes or reject and feedback.", 422)
        with Session(self.engine) as db:
            self.access(db, ticket_id, actor)
            t = self.lock_ticket(db, ticket_id)
            if t.status == "done":
                raise ApprovalError("The approved final document is immutable.")
            c = db.exec(select(ApprovalConflict).where(ApprovalConflict.ticket_id == ticket_id, ApprovalConflict.trigger_id == trigger_id).with_for_update()).first()
            reviewer = db.get(Reviewer, (ticket_id, c.arbiter)) if c else None
            if not c or not reviewer or reviewer.user_id != actor:
                raise ApprovalError("Only the fixed conflict arbiter can decide.", 403)
            if c.status != "pending":
                raise ApprovalError("This conflict already has an arbitration decision.")
            affected = []
            for department in c.department_ids:
                b = db.exec(select(ApprovalBranch).where(ApprovalBranch.ticket_id == ticket_id, ApprovalBranch.department_id == department).with_for_update()).one()
                if b.version != c.versions[department] or b.response or (decision == "request_changes" and b.revision_count >= MAX_REVISIONS):
                    raise ApprovalError("Refresh the conflict; its version changed or revision limit was reached.")
                b.response = {"decision": decision, "version": b.version, "feedback": c.resolution + " Human arbitration: " + feedback,
                              "actor": actor, "request_id": str(uuid4())}
                b.approval_status = "pending"
                db.add(b)
                affected.append(department)
            c.status, c.actor = decision, actor
            db.add(c)
            self.trace(db, ticket_id, None, "fixed_arbiter_decision", {"trigger_id": trigger_id, "actor": actor}, {"decision": decision, "departments": affected, "feedback": feedback})
            db.commit()

    def claim(self, ticket_id, department):
        token = str(uuid4())
        with Session(self.engine) as db:
            result = db.exec(update(ApprovalBranch).where(ApprovalBranch.ticket_id == ticket_id, ApprovalBranch.department_id == department,
                ApprovalBranch.approval_status.notin_(["approved", "rejected", "blocked"]),
                or_(ApprovalBranch.lease_until == None, ApprovalBranch.lease_until < now())).values(token=token, lease_until=now()+timedelta(minutes=12), error=None))
            db.commit()
            return token if result.rowcount == 1 else None

    def release(self, ticket_id, department, token, error=None):
        with Session(self.engine) as db:
            branch = db.get(ApprovalBranch, (ticket_id, department))
            # A crash after the decision commit does not undo a successful sign-off.
            if branch and branch.approval_status == "approved":
                error = None
            db.exec(update(ApprovalBranch).where(ApprovalBranch.ticket_id == ticket_id, ApprovalBranch.department_id == department,
                ApprovalBranch.token == token).values(token=None, lease_until=None, error=error))
            db.commit()

    def apply(self, ticket_id, department, token, response):
        with Session(self.engine) as db:
            self.lock_ticket(db, ticket_id)
            b = db.exec(select(ApprovalBranch).where(ApprovalBranch.ticket_id == ticket_id, ApprovalBranch.department_id == department).with_for_update()).one()
            if b.token != token or b.version != response["version"]:
                raise ApprovalError("Obsolete approval worker.")
            if b.approval_status in {"approved", "rejected", "revising"} and not b.response:
                return
            decision = response["decision"]
            b.approval_status = {"approve": "approved", "reject": "rejected", "request_changes": "revising"}[decision]
            b.response = None
            if decision == "approve":
                b.approved_version, b.approver, b.approved_at = b.version, response["actor"], now()
            self.sync_section(db, b)
            db.add(b)
            self.trace(db, ticket_id, department, "record_decision", response, {"approval_status": b.approval_status})
            db.commit()

    def revised(self, ticket_id, department, token, old_version, draft, evaluation):
        with Session(self.engine) as db:
            self.lock_ticket(db, ticket_id)
            b = db.exec(select(ApprovalBranch).where(ApprovalBranch.ticket_id == ticket_id, ApprovalBranch.department_id == department).with_for_update()).one()
            if b.token != token:
                raise ApprovalError("Obsolete revision worker.")
            if b.version > old_version:
                return b
            if b.revision_count >= MAX_REVISIONS:
                raise ApprovalError("Human revision limit reached.")
            self.trace(db, ticket_id, department, "revise", {"draft": b.draft, "evaluation": b.evaluation, "version": b.version}, {"draft": draft, "evaluation": evaluation, "version": old_version+1})
            b.version += 1
            b.revision_count += 1
            b.draft, b.evaluation, b.approval_status = draft, evaluation, "pending"
            b.approved_version, b.approver, b.approved_at = None, None, None
            self.sync_section(db, b)
            db.add(b)
            db.commit()
            db.refresh(b)
            return b

    def complete(self, ticket_id):
        self.arbitrate(ticket_id)
        with Session(self.engine) as db:
            t = db.exec(select(Ticket).where(Ticket.ticket_id == ticket_id).with_for_update()).one()
            if db.get(FinalDocument, ticket_id):
                return
            rows = list(db.exec(select(ApprovalBranch).where(ApprovalBranch.ticket_id == ticket_id)).all())
            active = db.exec(select(DepartmentSection).where(DepartmentSection.ticket_id == ticket_id)).all()
            pending = db.exec(select(ApprovalConflict).where(ApprovalConflict.ticket_id == ticket_id, ApprovalConflict.status != "resolved")).first()
            if not rows or {b.department_id for b in rows} != {s.department_id for s in active} or pending or any(b.approval_status != "approved" or b.approved_version != b.version or not b.evaluation.get("overall_pass") for b in rows):
                t.status, t.stage = "waiting_for_approval", "Department approval or changes pending"
                db.add(t)
                db.commit()
                return
            meta = db.get(RFPMetadata, ticket_id)
            currency = {"US": "USD", "ES": "EUR"}.get(meta.client_country)
            if not currency:
                raise ApprovalError("Verified country currency is required.")
            text = f"# TrackFlow logistics proposal\n\nClient: {meta.client_name or 'Client'}\n\nCurrency: {currency}\n\n"
            for b in sorted(rows, key=lambda x: x.department_id):
                text += f"## {b.department_id.title()}\n\n{b.draft['content']}\n\n"
            versions = {b.department_id: b.version for b in rows}
            db.add(FinalDocument(ticket_id=ticket_id, sections=versions, currency=currency, content=text))
            t.status, t.stage, t.updated_at = "done", "Final approved proposal available", now()
            db.add(t)
            self.trace(db, ticket_id, None, "final_document_synthesizer", {"approved_versions": versions}, {"currency": currency, "content": text})
            db.commit()

    def details(self, ticket_id, actor):
        with Session(self.engine) as db:
            t = self.access(db, ticket_id, actor)
            branches = list(db.exec(select(ApprovalBranch).where(ApprovalBranch.ticket_id == ticket_id)).all())
            conflicts_ = list(db.exec(select(ApprovalConflict).where(ApprovalConflict.ticket_id == ticket_id)).all())
            reviewers = list(db.exec(select(Reviewer).where(Reviewer.ticket_id == ticket_id)).all())
            assignments = {r.department_id: r.user_id for r in reviewers}
            document = db.get(FinalDocument, ticket_id)
            sections = []
            for b in branches:
                data = b.model_dump(exclude={"ticket_id", "token", "lease_until", "response"})
                data.update(owner=OWNERS[b.department_id], can_decide=assignments.get(b.department_id) == actor and b.approval_status == "pending" and not b.response,
                            can_approve=bool(b.evaluation.get("overall_pass")) and not any(b.department_id in c.department_ids and c.status != "resolved" for c in conflicts_))
                sections.append(data)
            return {"ticket_id": ticket_id, "status": t.status, "sections": sections,
                    "error": next((b.error for b in branches if b.error), None),
                    "blocked": any(b.approval_status == "rejected" or (b.revision_count >= MAX_REVISIONS and not b.evaluation.get("overall_pass")) for b in branches),
                    "can_start": t.owner_id == actor and not db.get(ApprovalRun, ticket_id) and t.status in {"under_evaluation", "needs_human_review"},
                    "can_assign": t.owner_id == actor, "reviewers": [r.model_dump(exclude={"ticket_id"}) for r in reviewers],
                    "conflicts": [dict(c.model_dump(exclude={"ticket_id"}), arbiter_name=OWNERS[c.arbiter], can_resolve=assignments.get(c.arbiter) == actor and c.status == "pending") for c in conflicts_],
                    "trace": [r.model_dump(exclude={"ticket_id"}) for r in db.exec(select(ApprovalTrace).where(ApprovalTrace.ticket_id == ticket_id).order_by(ApprovalTrace.timestamp)).all()],
                    "document": document.model_dump(exclude={"ticket_id"}) if document else None}
