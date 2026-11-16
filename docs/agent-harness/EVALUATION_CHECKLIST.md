# Part 2 evaluation checklist

| Course evaluation | Status | Implementation / verification |
| --- | --- | --- |
| Same company agent, identity, tools and KB | Confirmed | mcps/agent.py extends its existing graph; fixed TrackFlow CX identity; existing MCP tool enums/fields, knowledge pipeline and memory reused. Authenticated API now uses this same secured graph. |
| Out-of-domain questions redirect | Confirmed | Brief trivia/general-logistics answers append company purpose; unrelated tasks are refused with redirect. Deterministic input tests and captured casual/general-logistics scenarios. |
| At least three instruction-change variants rejected | Confirmed | The three quoted variants in README/PR are blocked before retrieval/model/tool execution. Unicode, Spanish and disclosure variants are tested too. |
| Personal chatbot requests rejected, legitimate support useful | Confirmed | Essays, poems, homework, unrelated coding and personal-advice cases refused. Authorized policy and MCP resource scenarios remain functional. |
| More than one guardrail | Confirmed | Independent input structure/scope/security, ownership/country, tool argument/result, external-content, memory and final-output layers. |
| Tool/RAG content never receives system authority | Confirmed | Fixed local tool schemas ignore external metadata; external injection fixtures are quarantined before model context; RAG data/metadata are isolated and markup escaped; recalled memory is filtered. |
| Deterministic automated tests; live LLM not sole gate | Confirmed | tests/agent_harness covers guards, fixed external fixtures, API and memory interactions. CI clears provider credentials and fails on failed assertions. Optional live smoke is separately labeled. |
| Every block/redirect logged with failure type | Confirmed | Separate privacy-safe event ledger with structural/content/security and block/redirect; tests inspect columns, sensitive-data absence and persistent summary counts. Captured scorecard contains actual counts. |
| Company fields, KB topics and restrictions respected | Confirmed | Both B2B/B2C authorization, actual resource country, carrier commercial secrecy and warehouse protection tested. Existing backend enums/UUID fields reused; no fabricated country-specific return policy or customer ownership data. |

Additional required evidence:

- [x] Full assignment and TrackFlow briefing copied beside the other contexts.
- [x] Order #45821 rejected as unauthorized, with no lookup or existence disclosure.
- [x] Spain policy override rejected for an actual US order; resource country takes precedence over profile country.
- [x] Raw questions, private record references and credentials excluded from the guardrail ledger.
- [x] Summary command exposes actual retained event counts per test session.
- [x] Part 1 approved and rejected live cycles continue through the secured graph.
- [x] Deterministic scorecard and optional real-provider smoke are clearly distinguished.
- [x] Final targeted regression suite and TypeScript check recorded in validation.txt.
- [x] Current branch retained and review materials prepared.

Production ownership note: the API accepts no client-provided grants and denies customer record lookup until a trusted server-side customer/order resolver is connected. Deterministic fixtures exercise the explicit positive authorization contract. Merge and course submission are not part of this checklist.
