# Milestone 9 Part 3 — human approval and completion

This extends the existing RFP ticket, API, backoffice, and reporting worker. Work stays on `Milestone-9`; the user opens the pull request.

## Workflow

1. Finish intake and Part 2 proposal generation. Retain the original intake and proposal handoffs.
2. The ticket creator assigns existing active TrackFlow account IDs to the named owners of the active departments. The fixed mapping is warehouse → Ana Whitfield; lastmile → Carlos Vega; reverse → Sofía Ramos. Assign Miguel Torres under `arbiter` when commercial arbitration is needed. Assignments are explicit trusted ticket delegation, recorded in the audit history; an account cannot claim a role in its decision payload. No authentication provider or login behavior changes.
3. Start department approvals in the existing RFP screen. Assigned users open their inbox or enter the ticket ID. Existing creator-only intake routes retain their access rules.
4. Each department gets its own LangGraph thread, `rfp-{ticket_id}:{department}`. A real `interrupt()` waits for that owner's decision, persisted in a durable checkpointer. Waiting releases the Celery task; it does not occupy a worker while a human is away. Another department can approve independently.
5. Approve, reject, or request changes on the displayed version. Rejection stops that department and blocks completion; request changes revises only that department using its existing generator and evaluators. There are at most **three additional human-requested revisions**, independent of Part 2's three-draft automated loop. Exhausted failing sections stay visible and cannot be approved. A human response is validated and saved before a background `Command(resume=...)` resumes the saved graph.
6. When all active current versions are approved, evaluations pass, and no conflict remains, automatically consolidate the approved section text into a stored Markdown `FinalDocument`. The renderer adds client/currency/headings; it does not use a model to alter signed-off terms. The same transaction stores the document and sets the ticket to `done`. Download it through the authenticated screen. Generation does not email or publish a client offer.

While a decision, correction, or rejected section remains outstanding, the ticket stays `waiting_for_approval` with per-section state and a blocked/error explanation. No new ticket lifecycle statuses are introduced. Prior drafts, evaluations, human feedback, actors and decisions remain in the persisted trace. Approvals record the exact version; revisions clear previous sign-off. The final artifact is immutable.

## Arbitration

The dedicated `arbitration` node detects structured contradictions; language models cannot vote them away.

| Trigger | Fixed decision owner | Required correction |
|---|---|---|
| `volume-vs-capacity` | Miguel Torres | Cap lastmile volume to confirmed warehouse capacity; request revised volume/cost. |
| `returns-sla-breach` | Sofía for a reverse-only breach; Miguel when another department embeds it | Request changes on every offending section; no sub-48-hour returns commitment. |
| `currency-mismatch` | Miguel Torres | Rewrite offending sections to USD for US or EUR for Spain. |

The fixed arbiter's authenticated decision is recorded, then affected branches revise and re-evaluate. Marking arbitration `request_changes` does not waive compliance. Unresolved contradictions keep the final gate closed. Capacity comparison requires matching units and periods, with quoted source evidence. A correction cannot hide its volume or remove an existing quoted customer total: that total must decrease in the same currency/billing period. Explicit commercial facts in authenticated human feedback are retained as source data for revisions; they cannot override business constraints. No SKU-to-order or pallet-to-order conversion, exchange rate or price is invented. Missing capacity remains an open commercial question; the system does not claim that an unprovided capacity has been verified. Older drafts without the optional structured commitments remain readable.

## Persistence and recovery

- Business entities are additive SQLModel tables on the existing PostgreSQL database: `rfp_approval_run`, `rfp_reviewer`, `rfp_approval_branch`, `rfp_approval_trace`, `rfp_approval_conflict`, `rfp_final_document`.
- Official `PostgresSaver` stores graph checkpoints on PostgreSQL. An advisory lock serializes initial checkpointer migrations when parallel workers start. Production does not use an in-memory saver.
- Local SQLite uses a companion `*.rfp-checkpoints.sqlite` file; file-backed local business state survives engine/process replacement. In-memory test databases use a temporary checkpoint file bound to their test engine.
- Explicit resume targets the saved thread. A per-department lease and fencing token protect duplicate/stale workers. Business mutations lock the ticket before its branch. Responses remain durable if dispatch fails; `/approvals/retry` requeues saved work and recovers finalization.
- No raw model/provider errors or credentials are returned. Node traces contain business input/output and timestamps and are available only to ticket participants. Uploaded customer documents and local runtime databases are not committed.

## API additions

All reuse normal `get_current_user` authentication.

| Method/path (under `/rfp`) | Purpose |
|---|---|
| `GET /approvals/inbox` | Assigned participant tickets |
| `GET /tickets/{id}/approvals` | Versions, evaluation, permissions, conflicts, history, final document |
| `POST /tickets/{id}/approvals/reviewers` | Creator assigns `{department_id,user_id}` |
| `POST /tickets/{id}/approvals` | Creator starts from completed Part 2 handoff |
| `POST /tickets/{id}/approvals/{department}/resume` | Owner sends `{decision,version,feedback}` |
| `POST /tickets/{id}/approvals/arbitrate` | Fixed arbiter sends `{trigger_id,decision,feedback}` |
| `POST /tickets/{id}/approvals/retry` | Participant retries saved processing |
| `GET /tickets/{id}/approvals/document` | Authenticated Markdown download after completion |

Unauthenticated requests return 401; unrelated tickets 404; wrong decision owner 403; malformed responses 422; stale versions, unresolved checks and duplicate decisions 409. Queue failure returns 503 after saving the command, with recovery instructions.

## Reproducible evaluation

Install locked dependencies with `uv sync --locked --group dev`. No model credentials are needed for these tests: fixtures are explicitly injected only in tests; production has no fake fallback.

```sh
uv run python -m pytest tests/pipelines/test_rfp_approval.py tests/pipelines/test_rfp_approval_api.py tests/pipelines/test_rfp_approval_recovery.py -q
```

`test_parallel_interrupt_resume_full_flow` reproducibly drives Parts 1→2→3 with the ModaViva fixture, pauses both departments, approves reverse while warehouse remains interrupted, then approves warehouse and verifies the final EUR document. Other tests cover file-backed restart, rejection, three revision rounds, provider interruption, owner isolation, version conflicts, all three arbitration triggers and API recovery. These simulated decisions demonstrate the software; they are not real employee approvals.

`test_pdf_upload_through_all_three_parts_and_authenticated_final_download` goes further: it creates a valid text PDF, uploads it through the actual HTTP intake endpoint, runs the real MarkItDown PDF converter, triggers proposal/approval endpoints and independent simulated owner resumes, then downloads the final EUR document. Only model responses, authentication actors and background dispatch are explicit test fixtures; the same persisted ticket passes through all three parts.

To exercise actual PostgreSQL checkpoints and concurrent decisions, set `TEST_RFP_DATABASE_URL` to an explicitly disposable PostgreSQL test database and run:

```sh
uv run python -m pytest tests/pipelines/test_rfp_approval_postgres.py -q
```

The existing `TrackFlow RFP intake` GitHub Actions workflow runs both suites, PostgreSQL tests, prior intake/proposal/agent/MCP regressions, typecheck and production build.

## Evidence and remaining live verification

Local deterministic integration checks do not establish that the Codespace's configured model, Supabase connection and Celery worker all work together. The last observed Codespaces access was blocked by the organization billing/budget issue. Recheck access and then run a real sample PDF through all three parts using the existing provider and actual reviewer accounts before claiming live-environment completion. Preserve the original Codespace's unrelated uncommitted agent-route/runtime changes when synchronizing.

Sources: [Part 3 assignment](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/projects/ai-eng-milestone-agentic-workflows-produce/README.md), [TrackFlow briefing](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/contexts/09-agentic-workflows/trackflow-BRIEFING.md).
