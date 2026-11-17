# Milestone 9 · Part 1 evaluation checklist

Branch: `Milestone-9`. No pull request is opened automatically. Parts 2 and 3 remain separate follow-up work on this same branch.

## Verified implementation

- [x] RFP UI lives in the existing backoffice, with thin App Router entry points.
- [x] Authenticated PDF upload returns HTTP 202 and saves one owned ticket before queuing work.
- [x] PDFs are size/signature/page checked, retained under ignored data/raw/rfp, and converted locally to Markdown before any agent runs.
- [x] Dedicated LangGraph classifier, orchestrator, parallel department workers, and synthesizer; the customer-support graph is unchanged.
- [x] Classifier accepts formal and informal client requests and rejects a supplier sales pitch.
- [x] Orchestrator shares metadata and department-relevant source excerpts. Exact source evidence and numeric grounding are validated before persistence.
- [x] Warehouse, last-mile, and reverse-logistics owners are fixed by the briefing.
- [x] PostgreSQL stores ticket state, metadata, department key aspects, and the structured Sales handoff atomically.
- [x] Pollable analyzing → intake_complete/discarded lifecycle. Failed/stalled jobs have bounded retries; lease claims prevent duplicate concurrent processing.
- [x] Readability metrics and approximate token counts are recorded, with language/availability limitations disclosed.
- [x] Sales summary, department contacts, questions, source evidence and stable ticket_id handoff are shown in the UI.
- [x] Owner isolation, invalid PDFs, classifier/worker output, retries, persistence, and PostgreSQL concurrency are covered by 31 passing tests.
- [x] TypeScript type check passed.
- [x] All three official PDFs passed a live configured-provider graph run: ModaViva → warehouse + reverse/EUR; LunaCosmetics → warehouse + lastmile/USD; supplier pitch → discarded.
- [x] ModaViva's 15,000 SKUs were not invented as monthly order volume.
- [x] Final production build passed (29 static pages, including the RFP route).
- [ ] All three PDFs uploaded and completed through the authenticated UI and Celery worker.
- [x] Branch-only GitHub Actions checks passed after push: 31 intake tests, 416 existing regressions, type check and production build.

## Evidence and limits

The live graph report is in evidence/live-graph.json. It uses the public curriculum samples and real configured model access; it is not an upload/UI test. Raw uploads and development logs are intentionally ignored.

The working tree contained an unrelated edit to services/routers/agent.py before this task. Four existing harness API tests fail against that edit; the committed baseline route passed all 416 targeted prior tests in an isolated in-memory comparison. That user edit is preserved and excluded from this milestone commit. Branch CI verifies the committed tree without an overlay.

Real background integration also passed against an isolated PostgreSQL database, Redis broker, Celery worker and configured model (see evidence/celery-check.json).

Text PDFs are supported. Encrypted, corrupt, oversized, overlong and scanned-only documents fail clearly; OCR is not implemented. Model/provider failures remain visible and retryable rather than producing fabricated results. No new authentication bypass or credential storage is introduced.
