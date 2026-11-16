# Milestone 8 Part 1 — evaluation checklist

- [x] User-created Milestone-8 branch retained; no extra branch created.
- [x] Full assignment and TrackFlow briefing copied to Contexts/CONTEXT_MILESTONE_8.md.
- [x] Architecture and rejected alternatives justified in README.
- [x] Durable separate store; no company RAG/knowledge writes.
- [x] Explicit read/propose/resolve/cleanup/audit interface.
- [x] Existing MCP-connected LangGraph extended; prior tools and RAG retained.
- [x] Structured final answer and optional proposal; explicit reusable-fact criterion.
- [x] Three memorable and three non-memorable examples documented.
- [x] Same-conversation proposal displayed before saving approved facts.
- [x] Structured decision, confidence threshold and proposal version binding.
- [x] One pending proposal; ambiguity/topic change/expiry never approves.
- [x] Edits need fresh approval; stale/retried decisions cannot double-write.
- [x] Audit includes safe candidate, source reference, principal, version, outcome and time.
- [x] Atomic audit-and-write; audit failure cannot save a fact.
- [x] Decision plus a new question continues; classifier cannot invent new requests.
- [x] Both B2B/B2C locations, warehouse routes, isolated-package data and negotiations checked before persistence.
- [x] Poisoning controls and limitations documented; memory is untrusted factual context.
- [x] Deduplication/supersession, category TTLs and hard growth limits functional.
- [x] Real approved cycle includes future-session effect.
- [x] Real rejected cycle includes logged rejection and unchanged facts.
- [x] New behavioral tests and existing RAG/LangGraph/MCP regressions pass (validation.txt).
- [x] TypeScript check passes (validation.txt).
- [ ] User review before assignment submission or merge.

Use the trusted scoped MCP CLI described in README; the existing web API remains memory-disabled. Part 2 now extends the same graph; see ../agent-harness/EVALUATION_CHECKLIST.md. The branch name follows the user's explicit choice instead of the assignment's example name.
