## task_054_orchestrate_actionable_and_truthful_cdx_tray_session_controls - Orchestrate actionable and truthful CDX tray session controls
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
- Summary: Orchestrate actionable and truthful CDX tray session controls
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Trace a session row from the capacity-sorted snapshot through the shared menu model, macOS custom cell, each native backend, and native/WSL terminal routing.
- [ ] 2. Define the smallest declarative session-action contract and submenu representation that retains stable session identity without turning the tray into a configuration editor.
- [ ] 3. Implement explicit open and configuration-view actions, capability-gated extension routing, and clear next-launch wording while preserving the existing global actions and alert behaviour.
- [ ] 4. Add focused identity, action-routing, unavailable-capability, and platform fallback tests; validate the tray and CDX command paths, then record the interaction boundary for the later Logics plugin work.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_090_add_an_explicit_capability_safe_action_submenu_to_every_tray_session_row`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_090_add_an_explicit_capability_safe_action_submenu_to_every_tray_session_row`. Proof deferred to slice closeout.
- request-AC2 -> `item_090_add_an_explicit_capability_safe_action_submenu_to_every_tray_session_row`. Proof deferred to slice closeout.
- request-AC3 -> `item_090_add_an_explicit_capability_safe_action_submenu_to_every_tray_session_row`. Proof deferred to slice closeout.
- request-AC4 -> `item_090_add_an_explicit_capability_safe_action_submenu_to_every_tray_session_row`. Proof deferred to slice closeout.
- request-AC5 -> `item_090_add_an_explicit_capability_safe_action_submenu_to_every_tray_session_row`. Proof deferred to slice closeout.
- request-AC6 -> `item_090_add_an_explicit_capability_safe_action_submenu_to_every_tray_session_row`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_043_make_cdx_tray_session_rows_actionable_without_misleading_live_settings`
- Product brief(s): `prod_032_actionable_cdx_tray_session_controls`
- Architecture decision(s): (none yet)
