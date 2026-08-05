## task_027_orchestrate_actionable_cdx_config_error_guidance - Orchestrate actionable cdx config error guidance
> From version: 0.12.1
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

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
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1, request-AC2, request-AC3, request-AC4 -> `item_036_improve_unknown_session_guidance_for_cdx_config`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# AI Context
- Summary: Orchestrate actionable cdx config error guidance
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_016_clarify_cdx_config_errors_for_unknown_sessions`
- Product brief(s): `prod_009_actionable_cdx_config_failures`
- Architecture decision(s): (none yet)
