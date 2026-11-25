# Part 3 evaluation checklist

Implementation evidence maps to the [official Part 3 evaluation](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/projects/ai-eng-milestone-agentic-workflows-produce/README.md).

- [x] A real human approval interrupt runs before department sign-off; durable checkpoints retain state.
- [x] Parallel independence: reverse approves while warehouse remains interrupted (`test_parallel_interrupt_resume_full_flow`, browser fixture).
- [x] Explicit authenticated resume continues the saved graph, including crash recovery at business-commit/checkpoint boundaries.
- [x] Thread identity includes both ticket and department; separate ticket namespaces cannot share a checkpoint.
- [x] Three additional human correction rounds are enforced; unresolved currency fails safely at the cap and cannot produce a document.
- [x] Dedicated arbitration node detects briefing triggers and uses the named fixed arbiter. Capacity conflicts track the supplying warehouse version, not just the lastmile draft.
- [x] Node trace retains agent, business input, output and timestamp, including review feedback and earlier draft versions.
- [x] Final synthesis requires approval of every active current version, passing evaluations, and no unresolved conflict. No model rewrites approved terms.
- [x] Ticket stays `waiting_for_approval` while pending and reaches `done` only when the final stored document is accessible.
- [x] Reproducible fixture integration path exists with simulated human resumes; no dependency on manual UI clicks or credentials.
- [x] The same ticket travels through Parts 1→2→3 in the integration test, retaining previous handoffs and current department scope.
- [x] HTTP integration additionally uploads a valid text PDF, executes real local PDF conversion, progresses all three parts, and downloads the final document.
- [x] Tests cover interruption/resume, iteration cap, arbitration, independent approval, restart persistence and duplicate/stale decisions.

Additional checks include authenticated reviewer assignment/inbox/download, unauthorized actor rejection, queue-failure recovery, finite quantities tied to quoted units/time periods, and preventing capacity corrections from dropping an existing customer total or retaining its higher cost.

## Evidence boundaries

- Local browser fixture used three separate isolated test accounts with normal login. Sofía approved first; Ana remained pending; Ana then approved and downloaded the final document; reload retained completion.
- Screenshots and the example document are **offline fixture evidence**, not customer proposals or actual employee sign-offs.
- PostgreSQL checkpoints/concurrent decisions, typecheck, production build and prior regressions run in the linked validation workflow; see `validation.json` for the exact checked code revision.
- [ ] Live Codespace model + Supabase + Celery E2E remains to be verified in that environment. The last observed Codespaces blocker was the organization billing/budget notice. Fixture/CI success does not establish this live check.

No pull request was opened; all three parts remain on `Milestone-9`.
