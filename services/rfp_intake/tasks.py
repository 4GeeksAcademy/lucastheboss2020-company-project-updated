"""RFP tasks use the existing Celery app and reporting queue; no new API process."""

from services.celery_app import app

TASK_NAME = "run_rfp_intake"


@app.task(name=TASK_NAME, bind=True, max_retries=2, acks_late=True, soft_time_limit=540, time_limit=600)
def run_rfp_intake(self, ticket_id):
    from services.database import engine
    from services.rfp_intake.store import Store
    from data.pipelines.rfp_intake.runner import process_ticket

    store = Store(engine)
    try:
        return process_ticket(store, ticket_id)
    except RuntimeError:
        if self.request.retries < 2:
            # Re-enable claim after the failed run. Only this ticket is retried.
            from sqlmodel import Session
            from .models import Ticket, now

            with Session(engine) as db:
                t = db.get(Ticket, ticket_id)
                if t and t.processing_state == "failed" and t.attempts < 6:
                    t.processing_state = "retrying"
                    t.stage = "Retry scheduled"
                    t.updated_at = now()
                    db.add(t)
                    db.commit()
            raise self.retry(
                exc=RuntimeError("RFP analysis temporarily unavailable"), countdown=10 * (2**self.request.retries)
            )
        raise
