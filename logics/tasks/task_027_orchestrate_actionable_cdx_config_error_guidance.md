## task_027_orchestrate_actionable_cdx_config_error_guidance - Orchestrate actionable cdx config error guidance
> From version: 0.12.1
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-05

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Capture the current text and JSON failures for unknown, missing, and extra config arguments.
- [ ] 2. Implement the smallest command-local message change that preserves error code and exit semantics.
- [ ] 3. Add focused tests for recoverable unknown-session text/JSON plus non-regression tests for usage and success.
- [ ] 4. Update any command reference that exposes error guidance if warranted.
- [ ] 5. Run focused CLI tests, relevant full checks, and Logics validation.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_036_improve_unknown_session_guidance_for_cdx_config`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- AC1 -> This task. Proof: missing-session config errors name the target and mention `cdx configs` and `cdx add`.
- AC2 -> This task. Proof: JSON failures preserve the standard error envelope and `unknown_session` code with actionable wording.
- AC3 -> This task. Proof: usage-error and success paths remain covered and unchanged.
- AC4 -> This task. Proof: focused tests and CLI documentation cover the updated config error wording.

# Validation
- (no validation recorded yet)
- Finish workflow executed on 2026-08-05.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-05.
- Linked backlog item(s): `item_036_improve_unknown_session_guidance_for_cdx_config`
- Related request(s): `req_016_clarify_cdx_config_errors_for_unknown_sessions`

# AI Context
- Summary: Orchestrate actionable cdx config error guidance
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_016_clarify_cdx_config_errors_for_unknown_sessions`
- Product brief(s): `prod_009_actionable_cdx_config_failures`
- Architecture decision(s): (none yet)
