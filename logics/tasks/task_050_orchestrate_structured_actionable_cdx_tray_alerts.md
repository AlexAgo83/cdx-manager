## task_050_orchestrate_structured_actionable_cdx_tray_alerts - Orchestrate structured actionable CDX tray alerts
> From version: 0.18.4
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# AI Context
- Summary: Orchestrate structured actionable CDX tray alerts
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Trace the current hook configuration, payload composition, JSONL spool, Rust parser, notification draw, history, and session action paths; confirm documented provider field availability.
- [ ] 2. Define the smallest backward-compatible structured event envelope and pure sanitization boundary, retaining the existing rendered title and message for fallback compatibility.
- [ ] 3. Update Codex and Claude provisioning to use the common Stop and PermissionRequest contract, eliminating the Claude duplicate-permission route.
- [ ] 4. Render structured completion and permission alert details and wire recent entries to the existing session-launch action without parsing display strings.
- [ ] 5. Add focused regression tests for privacy, provider parity, duplicate prevention, compatibility, and session actions; update concise documentation and run workflow and project validation.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`. Proof deferred to slice closeout.
- request-AC2 -> `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`. Proof deferred to slice closeout.
- request-AC3 -> `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`. Proof deferred to slice closeout.
- request-AC4 -> `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`. Proof deferred to slice closeout.
- request-AC5 -> `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`. Proof deferred to slice closeout.
- request-AC6 -> `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`. Proof deferred to slice closeout.
- request-AC7 -> `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_039_make_cdx_tray_agent_alerts_structured_and_actionable`
- Product brief(s): `prod_028_structured_actionable_tray_agent_alerts`
- Architecture decision(s): (none yet)
