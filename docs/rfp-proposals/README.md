# Milestone 9 Part 2 — proposal generation and evaluation

Part 2 extends the existing TrackFlow RFP workflow on `Milestone-9`. It consumes the saved Part 1 `ticket_id` and version-1 routing handoff. It never reads the PDF or performs a second intake analysis. No pull request is opened automatically.

## Flow and boundaries

`POST /rfp/tickets/{ticket_id}/proposal` requires the normal signed-in TrackFlow user and an owned `intake_complete` ticket with a ready Part 1 handoff. It returns 202 after saving the queued run. The existing Celery reporting queue executes `run_rfp_proposal`; there is no second API or production authentication override.

The dedicated graph stays under `data/pipelines/rfp_intake/`. WarehouseGenerator, LastMileGenerator, and ReverseGenerator have separate department instructions. Only departments selected in Part 1 run. Each receives shared metadata, its own key aspects, policy sources, and any previous draft/feedback. The customer-support graph is unchanged.

Each section runs readability, relevance, and compliance concurrently. Each evaluator returns its own result for the same section and draft version; results are combined after all three finish. Department branches revise independently. At most three saved draft versions are generated per department (initial plus two revisions). Passing sections stop immediately. Exhausted sections keep the latest content and complete EvaluationResult and enter the Part 3 handoff as `needs_human_review`; the ticket is never discarded because evaluation failed.

## Sources and checks

The four pinned Markdown policies in `docs/company-knowledge-base/` are supplied directly as generator/evaluator context. This uses the existing authoritative knowledge material without making optional semantic retrieval a new runtime dependency. Source files and production provider credentials are unchanged. The configured OpenAI-compatible provider is reused through its existing environment configuration; missing credentials fail clearly and never select a fake-model fallback.

Compliance uses fixed rule IDs and deterministic guards plus an independent model review of actual wording:

- `currency`: US → USD and Spain → EUR, including the draft prose.
- `delivery_sla`: supported 90% monthly on-time SLA, with delivery scope/exception review.
- `returns_minimum`: no returns-processing promise under 48 hours; express delivery is distinct.
- `discount_table`: volume tier table required; no unsupported numeric discounts or implied approval of preferential rates. Miguel Torres approves negotiation.
- `carrier_confidentiality`: no negotiated/internal carrier prices in customer-facing content.
- `source_grounding`: no unsupported numeric claims; the semantic evaluators additionally review capacity, services, dates, and other claims in context.

Unknown shipment charges, returns charges, capacity and discount percentages remain explicit open questions or pending quotations. Passing automated checks does not approve those terms or make a customer commitment. A pending quotation can be valid in a clearly provisional draft; Part 3 is responsible for human approval.

Readability uses the existing `py-readability-metrics` integration. Implementation targets are Flesch–Kincaid grade ≤14 and Gunning Fog ≤18, not course-prescribed thresholds. If formulas cannot run (short text or missing tokenizer), an explicit fallback requires at least 40 words, average sentence length ≤22 and longest sentence ≤40. The result identifies the method and never presents fallback sentence length as a formula grade. Metrics are English estimates.

## Persistence, statuses and recovery

Two additive SQLModel/PostgreSQL tables are created: `rfp_proposal_run` and `rfp_proposal_attempt`. No existing column migration or persistence-system replacement is required. Each version stores its structured draft and evaluation. Existing DepartmentSection `draft_content` and `evaluation_results` hold the latest version. Part 1's original Ticket.handoff remains unchanged; ProposalRun.handoff is the separate versioned Part 3 contract containing every selected section, its draft, evaluation, attempts and final per-section status.

The same ticket progresses from `intake_complete` to `drafting` and `under_evaluation`. On completion it remains `under_evaluation` with `processing_state=complete` and `ready_for_part3=true`, or becomes `needs_human_review` if any department exhausted its revisions. Part 2 never sets `waiting_for_approval`, `done`, or an approval decision.

Duplicate starts use a ticket compare-and-set plus PostgreSQL row lock. Claims use an atomic update. Every checkpoint and final write is fenced by a run token. JSON progress merges under the run lock, preventing parallel departments from overwriting each other. Failed or stalled runs can resume through `POST /rfp/tickets/{ticket_id}/proposal/retry`, with a maximum of six worker claims. Saved drafts awaiting evaluation are evaluated again without regenerating or spending another draft version. Already-passed/exhausted sections are reused. Queue failures retain the ticket and enable retry; stale jobs become retryable after 15 minutes. Provider errors are sanitized, and all saved history remains available.

The existing authenticated ticket GET/list responses add a `proposal` field with state, per-department progress, attempts/history, errors, retry eligibility and the Part 3 handoff. Private owner, broker, run-token and lease values are never exposed.

## Running and reviewing

Use the existing configured database/provider/Redis environment. Initialize additive tables before starting a worker with this version:

```sh
uv sync --locked --group dev
uv run --env-file backend/.env python scripts/init_rfp_tables.py       # review DDL
uv run --env-file backend/.env python scripts/init_rfp_tables.py --apply
uv run --env-file backend/.env uvicorn services.main:app --port 8000
uv run --env-file backend/.env celery -A services.celery_app worker --loglevel=INFO --concurrency=1 -Q reporting
```

Open the existing backoffice RFP screen, select an accepted intake ticket and choose **Generate proposal drafts**. The screen polls existing ticket data and displays drafts, owners, attempt counts, each evaluation, concrete feedback, history, resume controls and provisional/human-review notices. Plain text is escaped by React; model content is not injected as HTML.

## Verification and outstanding live check

Tests cover generators, parallel evaluator overlap, success, missing-aspect feedback, company-rule failures (including 24-hour returns), revision success, iteration exhaustion, retained drafts, provider interruption/resume, ownership, queue failure, duplicate commands, stale-token fencing and retry budgets. PostgreSQL-only integration tests verify fresh-session JSON/history persistence and concurrent start/claim uniqueness. They skip explicitly without a disposable `TEST_RFP_DATABASE_URL`; they do not silently substitute SQLite.

```sh
DATABASE_URL=sqlite:// REDIS_URL=redis://localhost:6379/15 uv run --no-sync python -m pytest tests/pipelines/test_rfp_proposal.py tests/pipelines/test_rfp_proposal_api.py tests/pipelines/test_rfp_proposal_postgres.py -q
npm run typecheck
npm run build
```

`examples.json` contains explicitly labelled deterministic model-fixture output: one passing evaluation and one failing the returns rule. It is not live-model evidence. Local browser verification used normal login in an isolated test account, fixture model injection and SQLite, and confirmed revision success, retained failure, feedback/history and reload visibility. The fixture launcher lives outside the repository and is never wired into production.

On 2026-11-21, GitHub blocked the existing Codespace because 4GeeksAcademy had not set or had exceeded its Codespaces budget. Implementation continued in a separate local checkout. The configured live-provider/database environment and Codespace worker remain unverified for Part 2 until that environment can start. No billing settings, authentication, environment files or deployment configuration were changed. The unrelated uncommitted Codespace edits were preserved.
