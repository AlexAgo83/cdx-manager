## task_065_orchestrate_grouped_tray_alerts_and_reliable_logics_viewer_actions - Orchestrate grouped tray alerts and reliable Logics viewer actions
> From version: 0.18.6
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-13 00:53:55
> Owner: Codex

# AI Context
- Summary: Deliver the two linked recovery paths in order: menu-only alert grouping, then detached repository-aware Logics viewer launches proven through the installed macOS tray.
- Keywords: orchestrate, grouped, tray, alerts, reliable, logics, viewer, actions
- Use when: Executing the request chain after the Logics Fleet viewer release is available.
- Skip when: The work is only a visual tray redesign or a Logics server implementation.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Trace the event-to-menu and plugin-card-to-action paths on macOS, then pin the current flat grouping and blocking/inert viewer failures with focused checks.
- [ ] 2. Implement the smallest menu-only alert grouping over the existing unread list, preserving its consultation boundary and stable action identity.
- [ ] 3. Extend the bounded first-party Logics row context and implement detached global Fleet and focused project viewer launches using the upcoming supported Logics CLI contract.
- [ ] 4. Exercise the installed macOS companion against real session alerts and both Logics actions; verify the browser opens, focused navigation targets the originating repository, and the tray remains responsive.
- [ ] 5. Record implementation evidence, update concise documentation if the user-visible behaviour changes, and run project plus Logics validation.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_107_group_unread_tray_alerts_by_their_originating_session`
- `item_108_launch_the_correct_logics_fleet_or_project_viewer_from_tray_actions`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_107_group_unread_tray_alerts_by_their_originating_session`. Proof deferred to slice closeout.
- request-AC2 -> `item_107_group_unread_tray_alerts_by_their_originating_session`. Proof deferred to slice closeout.
- request-AC3 -> `item_107_group_unread_tray_alerts_by_their_originating_session`. Proof deferred to slice closeout.
- request-AC4 -> `item_107_group_unread_tray_alerts_by_their_originating_session`. Proof deferred to slice closeout.
- request-AC8 -> `item_107_group_unread_tray_alerts_by_their_originating_session`. Proof deferred to slice closeout.
- request-AC5 -> `item_108_launch_the_correct_logics_fleet_or_project_viewer_from_tray_actions`. Proof deferred to slice closeout.
- request-AC6 -> `item_108_launch_the_correct_logics_fleet_or_project_viewer_from_tray_actions`. Proof deferred to slice closeout.
- request-AC7 -> `item_108_launch_the_correct_logics_fleet_or_project_viewer_from_tray_actions`. Proof deferred to slice closeout.
- request-AC8 -> `item_108_launch_the_correct_logics_fleet_or_project_viewer_from_tray_actions`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_054_group_tray_alerts_by_session_and_make_logics_actions_reliably_open_the_viewer`
- Product brief(s): `prod_041_contextual_cdx_tray_recovery_paths`
- Architecture decision(s): (none yet)
