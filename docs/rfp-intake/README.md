# TrackFlow RFP intake — Milestone 9 Part 1

Work stays on the user-created Milestone-9 branch for all three parts. The user will open the pull request. No PR, merge, deployment, approval workflow or course submission is performed by this implementation.

## Result

The existing backoffice at /uis/backoffice/rfp accepts customer PDFs, creates a durable ticket, and polls the existing services.main:app backend. The existing Celery app runs a dedicated LangGraph in data/pipelines/rfp_intake/. Business records live in the existing configured PostgreSQL/Supabase database, not in TinyDB or JSON-only files. PDF/Markdown sidecars under data/raw/rfp/ are ignored runtime artifacts.

Graph: PDF → local Markdown → classifier → orchestrator → parallel department workers → synthesizer → transactional save and Part 2 handoff. Rejected documents stop after the classifier and are marked discarded. Accepted documents finish as intake_complete. No proposal pricing or operational commitment is generated in Part 1.

Fixed departments: warehouse / Ana Whitfield; lastmile / Carlos Vega; reverse / Sofía Ramos. Own-carrier requests must not activate lastmile. Unknown services become open questions, not invented departments. Missing order volume is never inferred from an SKU count.

## Start in the existing development environment

Use uv sync --locked --group dev. Existing backend/.env supplies DATABASE_URL and the already-configured RAG_API_BASE_URL, RAG_API_KEY and RAG_GENERATION_MODEL. Do not put provider credentials in browser code or commit environment files.

Start the existing Redis instance, then run these in separate terminals:

    REDIS_URL=redis://127.0.0.1:6379/0 uv run --no-sync --env-file backend/.env python -m uvicorn services.main:app --host 0.0.0.0 --port 8000
    REDIS_URL=redis://127.0.0.1:6379/0 uv run --no-sync --env-file backend/.env celery -A services.celery_app worker --loglevel=INFO --concurrency=1 -Q reporting
    API_INTERNAL_URL=http://localhost:8000 npm --prefix uis/backoffice run dev -- --hostname 0.0.0.0 --port 3001

Open the existing private forwarded port 3001, sign in normally, and visit /uis/backoffice/rfp. The generic existing /api/backend proxy is reused. No new API process, public port, authentication scheme or secret is required.

For English-formula readability scores, install the NLTK data once:

    uv run --no-sync python -c "import nltk; nltk.download('punkt_tab')"

PDF conversion uses MarkItDown locally with plugins disabled. Limits: 10 MB, 1–80 pages, 60,000 extracted characters. Password-protected, corrupt and image-only/no-text documents receive a processing error, not a false non-RFP classification. OCR is not implemented. Readability includes word/character counts, approximate tokens (characters/4), Flesch-Kincaid and Gunning Fog when available. English formulas are approximate for Spanish/mixed-language PDFs and not a billing or latency prediction. Short documents or missing tokenizer data retain counts with an explicit unavailable reason.

## Database and API

Additive tables rfp_ticket, rfp_metadata and rfp_department_section are created during existing API startup using the current SQLModel engine. Existing tables/contracts are retained. create_all creates missing tables; it is not an upgrade migration for future schema changes. scripts/init_rfp_tables.py prints the PostgreSQL DDL by default and applies this additive initialization only with --apply.

- POST /rfp/tickets: authenticated multipart file; quick 202 with the persisted ticket. PDF signature, extension, MIME and size are checked. The file is saved to a server-generated path. Conversion/agents run in the worker.
- GET /rfp/tickets?offset=0&limit=30: paginated requester-owned tickets.
- GET /rfp/tickets/{ticket_id}: owned status, metadata, sections and handoff.
- POST /rfp/tickets/{ticket_id}/retry: retry a saved failed or stalled ticket, without re-uploading.

The API uses existing get_current_user. Tickets are private to their uploading account; a shared Sales/team ACL is not yet modeled. Another account receives 404 and cannot list or retry the ticket. API responses omit the owner identifier, physical file path, hash and execution lease token. Multipart data is not logged.

## Truthful status, retries and crashes

Business status is analyzing, discarded or intake_complete in Part 1. Separate processing_state and error_code/error_message distinguish queued/running/retrying/failed processing from business rejection. Queue dispatch failure keeps the saved upload and exposes retry. A failed worker cannot write a success result. All final business records are committed together; partial department rows are not published.

Atomic database claims prevent duplicate execution from producing duplicate sections. A finite execution token/lease rejects stale results after a retry. Workers allow two automatic retries after transient analysis failures; at most six claimed executions are allowed across manual retries. Document conversion errors require user action. A missing progress update for 15 minutes is exposed as stalled and can be retried. There is no separate watchdog scheduler; the UI/status API reports a stall. A killed worker is not silently represented as complete.

## Agent boundaries and handoff

Each agent has a fixed role and Pydantic schema. Document content is JSON-encoded as untrusted source excerpts, separate from system authority. Source IDs resolve server-side to exact text. Unknown IDs, fabricated quotes, changed department identities and unsupported numerical claims fail validation. Locale thousands separators in source numbers are normalized for comparison. Workers receive shared metadata and relevant excerpts only. The intake agents have no operational write, email, browsing or inventory tools.

These checks are defense in depth, not a complete semantic proof. Source numeric membership alone does not prove every claim, and model classification can still require human review. No offline fake classifier is silently used when the configured model is unavailable.

The handoff is saved with schema_version=1, ticket_id, rfp_id, metadata/currency, readability_metrics, active sections with owners/key_aspects/source evidence/open questions, Sales summary, conflicts, next_step=proposal_generation and ready_for_part2. Part 2 can start without reparsing the PDF. Currency is mapped by code: US→USD, ES→EUR, unknown→null. Part 1 preserves customer requests as requests, not TrackFlow promises. Parts 2–3 will add generation/evaluation, peer approvals and fixed-arbiter conflict handling from the copied briefing.

## Test samples and checks

    uv run --no-sync python scripts/fetch_rfp_samples.py

This downloads public curriculum PDFs to /tmp/trackflow-rfp-samples; they are not pre-seeded business records. Upload them through the UI:

1. trackflow-request-1.pdf: ModaViva (Spain), warehouse + reverse, EUR, exclude lastmile, SKU count is not monthly order volume.
2. trackflow-request-2.pdf: Luna Cosmetics (Los Angeles), warehouse + lastmile, USD, approximately 5,000 monthly orders.
3. trackflow-request-3.pdf: supplier/carrier rate pitch, discarded with no workers.

Offline agents are explicitly injected fixtures in tests only:

    DATABASE_URL=sqlite:// REDIS_URL=redis://127.0.0.1:6379/15 uv run --no-sync python -m pytest tests/pipelines/test_rfp_intake.py tests/pipelines/test_rfp_api.py -q

For PostgreSQL roundtrip and concurrent-claim tests, explicitly set TEST_RFP_DATABASE_URL to a disposable PostgreSQL test database and include tests/pipelines/test_rfp_postgres.py tests/pipelines/test_rfp_task_entrypoint.py. These tests never fall back to SQLite. The branch workflow provides isolated PostgreSQL and Redis and needs no model secrets. Optional real-model graph smoke:

    uv run --no-sync --env-file backend/.env python scripts/smoke_rfp_intake.py

See EVALUATION_CHECKLIST.md and validation artifacts for what was actually verified. Existing local edits in services/routers/agent.py predated this work and are preserved. They caused four existing harness API failures during the initial broad check; the committed HEAD route passed all 416 prior targeted tests in an isolated in-memory baseline check without changing that local file. Do not present a test with a fixture or baseline override as a live UI test.
