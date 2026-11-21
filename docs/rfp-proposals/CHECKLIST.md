# Part 2 evaluation checklist

- [x] Separate warehouse, lastmile and reverse generators, invoked only for departments selected in Part 1.
- [x] Input uses ticket_id + the saved synthesizer/key_aspects handoff; no PDF re-ingestion.
- [x] Readability, relevance and company-compliance evaluators run concurrently per draft.
- [x] Independent department revision loops send actionable feedback to their own generator.
- [x] Three-version limit; exhausted drafts/evaluations retained and marked needs_human_review.
- [x] Existing ticket status/progress updated; passing automated checks does not imply human approval.
- [x] Structured EvaluationResult: department/section, version, readability, relevance, compliance, overall_pass, feedback.
- [x] Additive PostgreSQL tables and existing section fields persist drafts and evaluations through the existing services API.
- [x] Tests exercise success, evaluation failure, and a specific TrackFlow returns-compliance failure.
- [x] Company-specific currency, SLA, returns, discount, carrier-confidentiality and grounding rules.
- [x] Duplicate commands, stale workers and bounded recovery tested.
- [x] Local browser fixture: revision then pass, retained exhausted draft, history, feedback and reload visibility.
- [x] TypeScript check and production build passed locally.
- [ ] PostgreSQL and full committed-branch regressions: awaiting branch CI result.
- [ ] Live configured-provider + Codespace/Supabase check: blocked by the organization's Codespaces billing/budget issue.

Branch: Milestone-9. No PR opened. See README.md for architecture, evidence limits, setup and test commands; examples.json for passing/failing fixture examples.
