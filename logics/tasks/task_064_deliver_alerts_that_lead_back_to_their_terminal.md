## task_064_deliver_alerts_that_lead_back_to_their_terminal - Deliver alerts that lead back to their terminal
> From version: 0.18.6
> Schema version: 1.0
> Status: In progress
> Understanding: 95%
> Confidence: 90%
> Progress: 80%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: Codex

# AI Context
- Summary: Carry safe terminal-origin metadata from an alert to an honest native focus action.
- Keywords: alert origin, terminal identity, stale alert, macOS notification
- Use when: Implementing alert focus behavior or notification click parity.
- Skip when: Changing alert delivery volume or mute preferences.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Confirm on the development host what a hook can observe: no tty on any descriptor, and which terminal variables survive into it.
- [ ] 2. Extend structured_details with the terminal identity, arguing the addition in the module's own terms, and publish it in the alert.
- [ ] 3. Add the focus action to alert rows, implement the macOS iTerm2 path, and render unavailability with its reason everywhere else.
- [ ] 4. Probe Terminal.app and record the finding, supported or not, rather than leaving it open.
- [ ] 5. Add the macOS notification delegate so a banner click resolves through the same path as the row.
- [ ] 6. Run the Python suites, the Rust tray suite and the tray smoke script, and document the behaviour and its authorization prompt.
- [ ] 7. Treat terminal identity as untrusted structured metadata: validate it at receipt and click time, and prove stale retained alerts cannot fall back to a different window.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_104_record_which_terminal_a_hook_fired_from_and_carry_it_to_the_tray`
- `item_105_focus_the_originating_terminal_from_a_tray_alert_row`
- `item_106_make_the_notification_banner_act_like_the_alert_row_on_macos`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_104_record_which_terminal_a_hook_fired_from_and_carry_it_to_the_tray`. Proof deferred to slice closeout.
- request-AC6 -> `item_104_record_which_terminal_a_hook_fired_from_and_carry_it_to_the_tray`. Proof deferred to slice closeout.
- request-AC7 -> `item_104_record_which_terminal_a_hook_fired_from_and_carry_it_to_the_tray`. Proof deferred to slice closeout.
- request-AC2 -> `item_105_focus_the_originating_terminal_from_a_tray_alert_row`. Proof deferred to slice closeout.
- request-AC3 -> `item_105_focus_the_originating_terminal_from_a_tray_alert_row`. Proof deferred to slice closeout.
- request-AC4 -> `item_105_focus_the_originating_terminal_from_a_tray_alert_row`. Proof deferred to slice closeout.
- request-AC5 -> `item_106_make_the_notification_banner_act_like_the_alert_row_on_macos`. Proof deferred to slice closeout.
- request-AC8 -> `item_104_record_which_terminal_a_hook_fired_from_and_carry_it_to_the_tray`. Proof deferred to slice closeout.
- request-AC9 -> `item_105_focus_the_originating_terminal_from_a_tray_alert_row`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_053_bring_back_the_terminal_an_alert_came_from`
- Product brief(s): `prod_040_alerts_that_lead_back_to_their_terminal`
- Architecture decision(s): (none yet)
