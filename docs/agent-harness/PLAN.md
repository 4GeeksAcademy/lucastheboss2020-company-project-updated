# Milestone 8 Part 2 implementation plan

Scope: extend the same TrackFlow first-line CX MCP/LangGraph agent, retain approved memory and work on the existing Milestone-8 branch. Read the full assignment and company briefing before coding; copies are in Contexts/CONTEXT_MILESTONE_8_PART_2.md.

1. Inspect the current agent, MCP contracts, RAG guardrails, authentication and resource ownership sources. Preserve current API field names and the prior memory flow.
2. Add deterministic input protections separating legitimate company support, brief casual/logistics questions, unrelated personal tasks and instruction-change attacks.
3. Bind customer-specific requests to trusted company/subject/resource grants and actual order country. Missing ownership information fails closed; do not invent an ownership mapping from internal inventory operator IDs.
4. Constrain MCP execution with static trusted schemas, capabilities, request-bound IDs, client/country checks and verified results. Isolate tool/document/memory content as data before any model consumes it.
5. Validate output structure, sensitive disclosure, country, citations and numeric evidence. Prevent a later memory evaluation step from undoing a previously checked answer.
6. Record privacy-safe typed guard events and expose a session summary command. Keep raw messages, credentials and customer records out of the ledger.
7. Add deterministic guard/isolation/API/memory regressions and a credential-free CI gate. Capture required scenarios with honest fixture provenance, plus optional configured-model smoke and a Part 1 live regression.
8. Document every evaluation, inspect the diff for secrets/runtime files, commit/push the same branch and prepare a pull request for review. Leave merge and submission to the user.

Implementation and local evidence are complete; current automated results are in validation.txt and the pull request checks. Production customer record resolution remains a fail-closed integration contract because the repository has no authoritative customer ownership source.
