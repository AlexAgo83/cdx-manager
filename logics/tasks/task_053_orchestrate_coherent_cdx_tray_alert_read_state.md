## task_053_orchestrate_coherent_cdx_tray_alert_read_state - Orchestrate coherent CDX tray alert read state
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
- Summary: Orchestrate coherent CDX tray alert read state
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Trace fresh event collection, spool acknowledgement, history merging, marker rendering, and the native menu lifecycle available on macOS, Windows, and Linux.
- [ ] 2. Model the smallest volatile unread state with an explicit consultation boundary; prove that delivery acknowledgement and reading remain separate.
- [ ] 3. Wire each backend's menu-open and menu-close handling to the shared state, retaining late-arriving events and failing safe when lifecycle observation is unavailable.
- [ ] 4. Add focused state and backend regression tests, update concise tray behavior documentation, and run Rust, project, and Logics validation.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_089_unify_tray_alert_marker_and_recent_alert_read_state`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_089_unify_tray_alert_marker_and_recent_alert_read_state`. Proof deferred to slice closeout.
- request-AC2 -> `item_089_unify_tray_alert_marker_and_recent_alert_read_state`. Proof deferred to slice closeout.
- request-AC3 -> `item_089_unify_tray_alert_marker_and_recent_alert_read_state`. Proof deferred to slice closeout.
- request-AC4 -> `item_089_unify_tray_alert_marker_and_recent_alert_read_state`. Proof deferred to slice closeout.
- request-AC5 -> `item_089_unify_tray_alert_marker_and_recent_alert_read_state`. Proof deferred to slice closeout.
- request-AC6 -> `item_089_unify_tray_alert_marker_and_recent_alert_read_state`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_042_synchronize_cdx_tray_alert_badges_with_menu_reading`
- Product brief(s): `prod_031_coherent_cdx_tray_unread_alerts`
- Architecture decision(s): (none yet)
