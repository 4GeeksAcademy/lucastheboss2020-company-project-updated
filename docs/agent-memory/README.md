# TrackFlow — Milestone 8, Part 1

The existing MCP-connected LangGraph assistant now remembers approved operational corrections and recurring B2B reporting preferences across restarts and conversations. A proposal is never an approved fact: explicit approval of the pending version and its audit entry must commit together before the fact becomes retrievable.

The user-created branch is **Milestone-8**, serving the role called feature/agent-memory in the assignment. Part 2 now adds the [protection harness](../agent-harness/README.md) to this same graph; this document describes the retained Part 1 memory design. The full copied assignment, TrackFlow briefing and approved design choices are in [CONTEXT_MILESTONE_8.md](../../Contexts/CONTEXT_MILESTONE_8.md).

## Architecture

This extends **the same graph in mcps/agent.py**, not another agent. Operational requests still discover and invoke tools through MultiServerMCPClient; inventory stays read-only. Existing grounded RAG remains a read-only knowledge path. Neither company Qdrant collections nor the separate earlier services/agent checkpoint/trace implementation are memory storage.

Current memory-enabled path: input_guard → memory_prepare → route → knowledge/tools → memory_evaluate → output_guard → END. Confirmation-only messages skip RAG/tools after memory_prepare and still pass through output_guard. A decision plus a question resolves the proposal then continues normally. The classifier's continuation must be a verbatim substring of the actual user message; it cannot invent a new request. A question containing a question mark is preserved even if the classifier omits it.

The existing grounded/tool answer is retained as a draft. One additional structured final-response call returns Evaluation(answer, memory_proposal) together. A structured Decision call runs only when a proposal is pending. This preserves existing RAG/MCP behavior without another graph, another agent, or a self-editing system prompt. Optional evaluation failure preserves the grounded draft. A memory backend failure does not prevent the existing operations path from responding.

### Why SQLite

A dedicated durable database at services/agent_memory/runtime/trackflow_agent_memory.sqlite provides a structured key-value/fact store, proposals, and audit tables. SQLite offers transactions and persistence without another credential or service. At TrackFlow's scale (eight carriers, two countries, bounded reporting preferences), exact keys and limited lexical selection are sufficient. Vector retrieval adds approximation and infrastructure without a large semantic corpus; company knowledge vectors must remain untouched. Redis adds deployment/persistence configuration; a graph database adds relationships we do not query. Fine-tuning does not support immediate user approval, provenance, targeted expiry or forgetting. Chat context and checkpoints are not approved persistent memory.

The explicit store interface is propose / pending / resolve / recall / cleanup / audit. Facts are keyed by category + country + normalized entity, notably **carrier + country**, rather than ticket. An approved correction supersedes that key. The proposal discloses the previous saved fact before replacement; versioned audit snapshots retain previous proposals. Unrelated carrier zones should be summarized in the proposed fact before authorizing replacement: this is a latest-confirmed-fact model, not an automatic merge of conflicting claims.

## Running a conversation

Load the configured provider privately. Never paste credentials into prompts, evidence or Git. Run the existing Qdrant service for the real knowledge path, and the existing OAuth MCP server for incident/inventory requests.

Example using a synthetic preference:

    uv run --no-sync --env-file backend/.env python -m mcps.agent --company trackflow --actor cx-evaluator --conversation demo-a "The cosmetics client in Spain always wants monthly reports with returns breakdown first."

Read the proposal, then run the same command with the same three identifiers and the message “Yes, remember that preference.” Use a different conversation identifier, such as demo-b, to ask about that client's report in a later session. The same company and actor retrieve approved facts across sessions. The optional --memory-db flag selects another dedicated SQLite path.

All three scope flags are required together. **They are trusted local CLI/operator inputs, not authentication.** An integrating application must derive company/actor from its authenticated server-side identity, never chat text. There is no shared default memory user. Actors and companies are isolated; this version does not share preferences across staff. A new conversation discards the principal's unresolved old proposal by default.

Calling ask(question), or omitting all scope flags, is memory-disabled but now protected by the Part 2 harness. The /agent/query endpoint now invokes the same secured MCP graph while retaining its authentication and response fields; it remains memory-disabled and does not accept client ownership grants. No public endpoint, credential, or permission is added.

## Self-evaluation and restrictions

Propose only a **new/corrected, concrete, reusable fact explicitly supplied by the current user**, not a question, speculation, inferred tool result, policy change or one-time task. Most turns have no proposal.

Memorable examples:

1. SEUR no longer covers rural Zaragoza; the local carrier is now assigned there (carrier rule, ES).
2. Repeated Los Angeles delays this week are due to a port strike, not an internal TrackFlow incident (temporary recurring incident, US).
3. The cosmetics client always wants returns breakdown before shipment volume in monthly reports (B2B reporting preference, ES).

Non-memorable examples:

1. “Where is the package with tracking XJ4471?” — isolated tracking query.
2. “Great, that's resolved.” — closure.
3. “Translate this into English for the client.” — single-use task.

Never persist **sensitive exact locations for B2B brands or B2C recipients**, internal warehouse routes/layouts, isolated package incident details, active commercial negotiations, secrets, or policy/instruction overrides. The model is instructed to reject the whole source for memory when it contains forbidden information. The store independently applies conservative content validation to the source and candidate. A safe-looking fragment extracted from a forbidden source is also blocked. This boundary covers pending proposals, revisions, facts and audit payloads.

Raw user messages and raw decisions are not written to this memory database. Audit records contain a SHA-256 originating-message reference, principal/conversation, proposal ID/version, safe candidate snapshot, event and timestamp. This MCP graph has no persistent raw-message checkpoint or tracing hook. The unrelated legacy trace implementation is unchanged and is not used by this flow.

Semantic checks plus conservative text validation are defense in depth, **not a universal PII detector or independent verification of carrier truth**. Unknown sensitive formats and sophisticated false factual corrections remain limitations. User-confirmed facts are low-trust operational context, never executable instructions, access grants, company policy, or authority to override RAG guardrails. Scope isolation, narrow categories and expiry limit their influence. The production ticket/review-team governance path is intentionally omitted by the course.

## Confirmation and audit

Only one pending proposal per company/actor is allowed, enforced by a SQLite unique partial index. The structured classifier returns approve/reject/edit/unrelated/uncertain. Approval requires confidence at least 0.9 and exact proposal ID/version binding. Silence, topic change, ambiguity, mismatched IDs, model failure and expiry never approve.

An edit is validated, logged, versioned and displayed for a fresh approval. Old-version approvals are stale. Approval plus its audit event commit atomically; an audit failure rolls back the fact. Concurrent/retried approvals cannot double-write. Rejection retains a safe audit record and leaves facts unchanged. Every proposal and outcome has a source reference and timestamp, including rejected, edited and expired proposals.

## Consolidation and forgetting

- Pending TTL: **10 minutes**. Cleanup runs on reads/writes and via cleanup(scope); abandoned proposals never become facts.
- Recurring incident TTL: **7 days**, fitting short-lived strike/operational context.
- Carrier/report preference TTL: **90 days**, requiring periodic reconfirmation as operations change.
- Exact duplicates do not create another proposal; approved new versions supersede the same structured key.
- Maximum **100 active facts per company/actor**. Expired facts are removed; overflow evicts the oldest update with deterministic tie ordering. Retrieval selects at most eight relevant facts, never full chat history.
- Safe proposal/audit history retains **365 days** and at most **10,000 records per principal** in each table. This is an inspectable transactional audit, not a tamper-proof compliance ledger. Runtime SQLite is ignored by Git; only synthetic evidence is committed.

## Validation and evidence

[CHECKLIST.md](CHECKLIST.md) maps deliverables. [validation.txt](validation.txt) contains actual check output. Reproduce:

    REDIS_URL=redis://127.0.0.1:6379/15 uv run --no-sync python -m pytest tests/agent_memory tests/pipelines/test_rag.py tests/pipelines/test_pipeline.py tests/pipelines/test_agent_graph.py tests/pipelines/test_offline_replay.py tests/mcps -q --tb=short
    npm run typecheck

[Captured cycles](../../data/eval/agent-memory-cycles.json) were produced by:

    uv run --no-sync --env-file backend/.env python -m scripts.capture_memory_cycles

The script uses the actual configured provider, existing graph and real RAG knowledge path with synthetic facts. It reopens SQLite and creates a fresh graph every turn. The approved cycle checks a future session's recall and answer ordering. The rejected cycle checks identical facts before/after and logged rejection. These report-preference turns do not invoke incident/inventory tools; existing MCP tests plus a new memory-enabled discovery test cover that boundary. Deterministic unit tests use explicit fake model/tool boundaries and are not presented as live evidence.

Additional live classifier evidence: [agent-memory-decision-probes.json](../../data/eval/agent-memory-decision-probes.json), reproducible using scripts/evaluate_memory_decisions.py. Seven actual-model probes cover quoted yes with rejection, uncertainty, conditional consent, topic change, approval plus a question, classifier prompt injection, and an edit without approval. All passed. Model-reported confidence is a decision gate, not a calibrated probability of truth.

Current combined validation and guardrails are documented in ../agent-harness/README.md and ../agent-harness/validation.txt. The original Part 1 validation is retained as historical evidence.
