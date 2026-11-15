# Milestone 8 — Part 1 context

Copied 2026-11-15. Assignment/reference documents; user authorizes Part 1 implementation on existing Milestone-8 branch.

## TrackFlow company briefing (full rendered text)
Source: https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/contexts/08-agent-engineering/memory/trackflow-BRIEFING.md

BRIEFING — TrackFlow
Milestone 8 · Part 1 · Agent Memory and Self-Improvement
Why this memory matters for TrackFlow

Your agent already knows TrackFlow's operations in Los Angeles and Zaragoza, queries the Incidents Manager and inventory through the MCP Server, and will get its harness in Part 2. Valentina Cruz (CX Manager) reports that her 15 support agents, split across both countries, have to correct the assistant on the same carrier rules over and over — the assistant doesn't learn from one session to the next.

What IS worth remembering
Corrected carrier assignment rules: if a carrier changed its coverage for a certain zone, or stopped operating a certain route, that's worth remembering.
Context from known, recurring incidents: "the delays on the Zaragoza-to-Catalonia route this week are due to a carrier strike, not a TrackFlow problem" — useful so the same alert isn't re-escalated.
Recurring B2B clients' preferences for their monthly report (format, highlighted metrics).
What must NEVER enter memory
Exact end-customer (B2C) addresses or internal warehouse routes — this is sensitive physical-security information, as the company's own guardrails README already flags.
Data from a single, non-repeating package incident (an isolated customer complaint isn't memorable).
Information from active commercial contract negotiations (that's handled by the commercial team's CRM, not the support agent's memory).
Examples for your "Self-Evaluation" checklist

Should generate a memory proposal:

"Actually SEUR no longer covers that rural area of Zaragoza, we've had to use the local carrier since last month."
"Those delays reported in Los Angeles incidents this week are from the port strike, not something on our end — that's the third ticket about it already."
"The cosmetics client always wants their monthly report with the returns breakdown first, before shipment volume."

Should NOT generate a proposal:

"Where's the package with tracking XJ4471?" (one-off tracking query, not a pattern).
"Great, that's resolved." (conversation closing).
"Translate this into English for the client." (single-use task).
Suggested consolidation

TrackFlow works with 8 carriers across two countries. Consider consolidating memory by carrier + country rather than by individual ticket, so assignment rules don't end up fragmented across dozens of loose entries.

Company constraints

TrackFlow distinguishes between B2B clients (brands) and B2C clients (end recipients). Your "what must never be remembered" validation must explicitly cover sensitive location data for both client types, not just one.

## Full assignment (rendered text)
Source: https://learn.4geeks.com/main-cohort/miami-ai-engineering-2/syllabus/agentic-engineering-miami/project/ai-eng-milestone-agentic-engineering?moduleId=3

0 / 29

This project has 29 tasks

To take advantage of this lesson better, look for the checkboxes and mark them as completed as you progress.

README
Milestone — Agent Memory and Self-Improvement (Part 1 of 2)

Before you start: Read your company-BRIEFING.md — it defines what information must never enter your agent's memory, and what kinds of facts are actually worth remembering at your company.

🎯 Your challenge

📌 You are building on your own fork of the company's monorepo selected at the beginning of the course — not on a new repository.

Your company already has a RAG knowledge base from an earlier milestone — a document store the model can consult. That is not the same product as this agent. The agent you extend here has its own identity (see your BRIEFING: manager support, CX, compliance, first-line support, …). It may call RAG as a tool; it does not become the commercial Q&A UI. The problem is that every conversation still starts from zero: it doesn't remember that a similar escalation was resolved yesterday, or that a user already corrected a piece of data last week. Your tech lead opened a ticket after two different clients had to repeat the same correction three times in the same week.

🧠 Complementary Knowledge: Memory Architectures

An agent's memory isn't a single component — it's organized by temporal scope. The context window is enough when the task fits in a single session. Episodic memory (Redis, key-value, prompt caching) lets the agent remember past interactions and personalize. A VectorDB retrieves semantically similar information across large corpora. Knowledge graphs matter when explicit relationships (dependency, hierarchy) are the actual retrieval requirement — something cosine similarity can't capture. Fine-tuning (parametric memory) is the last resort: expensive, slow to update, and it doesn't let you selectively "forget." No self-improving memory architecture works without a cleanup and consolidation cycle — without curation, raw accumulation degrades retrieval quality over time.

From: Tech Lead — Ticket #MEM-092

The agent already uses company knowledge (RAG as a tool, not as this agent's identity) and the MCP Server's tools. But every conversation starts from zero: it doesn't remember that we resolved a similar escalation yesterday, or that someone already corrected a piece of data last week. I need the agent to learn from interaction, without that meaning it starts making things up or piling junk into its memory forever.

You don't need a new graph or a multi-agent architecture for this — it's the same agent as always, with one extra self-evaluation step:

When the agent detects, within its own response, something worth remembering, it proposes it to the user in the same conversation ("want me to remember this for next time?") instead of writing it straight to memory.
That decision — yes, no, or an edit — can't be a fuzzy interpretation of the next message. It has to be explicitly classified against the pending proposal and logged: what was proposed, what the user decided, and when. If the decision can't be determined with reasonable confidence, the proposal is discarded by default — approval is never assumed from silence or ambiguity.
Only what's approved and logged gets consolidated into the persistent store; what's rejected is discarded, but the record that it was proposed and rejected stays.

I won't accept a memory that grows without limit, that self-edits without the user knowing, or a memory write with no trace of who authorized it.

⚠️ Disclaimer — Core memory in production: In a real company, core memory is not edited freely by any agent or developer. Changes go through modification request tickets and are reviewed/applied by a dedicated team that owns that control chain. For this project, that governance path is omitted on purpose so the milestone stays viable and achievable — you implement proposal → user confirmation → write/consolidate directly in your agent flow.

🔀 PR approved → merge it into main. Otherwise the feature never gets deployed, and your next branch starts from outdated code, which leads to merge conflicts.

🌱 How to Start the Project
If you already have your fork of the company's monorepo, create a new branch from your latest progress (MCP / LangGraph agent work).
If for some reason you don't have a fork yet (for example, you joined late or lost it), fork the reference monorepo before continuing.
1git switch -c feature/agent-memory
Keep building on the same LangGraph agent that already consumes the MCP Server — this project doesn't replace that base, it extends it.
Install any new dependency with uv add (never pip install or pipenv).
💻 What You Need to Do
Memory Architecture Selection
Choose a persistent memory backend (e.g. Redis, a key-value store, a VectorDB, or a combination) and document in writing why it fits what your agent needs to remember at your company.
Do not write memory into the company RAG collections (*_knowledge / company Qdrant knowledge store). RAG stays a read-only tool. Memory uses a separate store or a clearly named non-knowledge collection (e.g. Redis, KV, or *_agent_memory). Mixing episodic/approved facts into curated docs breaks retrieval evals and poison controls.
Implement an explicit read/write memory interface — the agent must not accumulate state by simply appending everything to the system prompt.

⚠️ IMPORTANT: Which facts are memorable and which are strictly forbidden to store must match exactly what's specified in your company-BRIEFING.md. A generic implementation that ignores those restrictions will not be accepted.

Self-Evaluation and Memory Proposal
After each relevant interaction, the agent must self-evaluate whether there's something new or corrected worth remembering, using an explicit criterion (not simply "always").
The simplest way to solve this is to ask the model for structured output in a single call: the response the user sees, plus a memory_proposal field (if applicable, what would be added/changed and why). You don't need a second model call, a separate agent, or a multi-agent architecture — it's the same agent with one additional output field.
The agent must be able to dismiss most interactions as "nothing to remember" — document at least 3 examples of interactions that should NOT generate a proposal.
When there is something memorable, the agent proposes it to the user within its own response (for example, as a question at the end) — it never writes directly to memory at this step.
User Confirmation and Auditable Log
When there's a pending memory proposal, the user's next message must first be evaluated against that proposal: does it approve, reject, or edit it? Use an explicit intent classification (structured label / classifier), not a plain "yes" in message.
There can only be one pending proposal at a time: if one is already unresolved, the agent must not launch a second one until the first is closed.
If the user changes topic without clearly responding yes or no, the proposal is discarded by default — approval is never assumed from silence or ambiguity.
Every decision (proposal, outcome, originating message, timestamp) is logged in an auditable way, regardless of whether the proposal was approved or rejected.
After resolving the pending proposal (in the same turn or a later one), the conversation continues normally — including cases where the user answers the proposal and asks another question in the same message.
Consolidation and Cleanup
Implement a consolidation mechanism that keeps memory from growing without control (e.g., summarizing, deduplicating, or discarding low-relevance entries).
Document the expiration or cleanup policy you applied and why you chose it.
Evidence
Document at least two complete cycles of the flow: one where a memory update is approved and reflected in a future interaction, and one where it's rejected and memory stays unchanged.
🎨 Design Decisions

As part of the challenge, your implementation must resolve — without being told explicitly in a checklist — the following decisions:

What kind(s) of memory (episodic, semantic/vector, knowledge graph) does your company actually need, and why did you rule out the other options?
What information should never enter the agent's memory, no matter who asks for it? Check your BRIEFING — some companies have non-negotiable restrictions here.
How does the agent decide what to forget, and what happens to a pending proposal if the user never responds?
How do you prevent a malicious user from "poisoning" the agent's memory with false information presented as a legitimate correction?
Why doesn't this require a multi-agent architecture to solve self-evaluation and the memory proposal? Justify your answer with what you implemented.
✅ What We Will Evaluate
The chosen memory architecture is justified in writing and matches what the agent actually needs to remember.
Memory writes never target company *_knowledge / company RAG collections (separate store or non-knowledge collection only).
There's an explicit read/write memory interface (not implicit memory via the system prompt).
The agent correctly distinguishes memorable interactions from non-memorable ones, with at least 3 documented examples of each type.
The memory proposal is communicated within the same conversation, not through a separate channel or process.
No memory update is written without an explicit, correctly classified user decision (not a naive text match).
Only one proposal is pending at a time, and silence or ambiguity resolves as rejection by default, not approval.
Every proposal and its outcome are logged in an auditable way, regardless of whether it was approved or rejected.
There's a documented, functional consolidation/cleanup mechanism.
At least two complete evidence cycles are delivered (one approved, one rejected).
The design decisions explicitly address the restrictions in your company-BRIEFING.md, especially what must never be remembered.
📦 How to Submit

Follow the standard Pull Request flow against your own fork of the monorepo:

Open a PR from feature/agent-memory to your main branch.
Include in the PR description the justification for your memory architecture and the answers to the design decisions.
Attach or describe the evidence for both complete cycles (approved and rejected).

This and many other projects are built by students as part of 4Geeks Academy's Coding Bootcamps. Find out more about our programs in Full-Stack Software Development, Cybersecurity, and AI Engineering.

## Approved implementation choices
- Extend the existing MCP-connected LangGraph agent, preserving RAG and tools.
- Separate durable SQLite memory store; never write to company RAG knowledge collections.
- Explicit structured self-evaluation/proposal and classified confirmation; no writes until logged approval.
- Scope by authenticated actor/company/conversation; one pending proposal; bind decisions to proposal version.
- Validate forbidden data before all persistence, including audit and traces. Cover B2B and B2C locations, warehouse routes, isolated package data, contract negotiations.
- Pending proposals expire after 10 minutes; recurring incidents after 7 days; carrier/report preferences after 90 days; bounded active facts and deduplication.
- Document at least 3 memorable/non-memorable examples; capture real approved/rejected cycles with future-session reuse.
- Revalidate edits and request approval again. Ambiguous/unrelated/silent responses never approve.
- Guard against poisoning; memory remains untrusted factual context, never policy/instructions.
- User created branch Milestone-8. Do not create/switch branches. Existing provider configuration is in backend/.env; load privately, never display secrets.
