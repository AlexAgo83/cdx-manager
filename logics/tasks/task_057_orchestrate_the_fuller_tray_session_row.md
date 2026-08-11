## task_057_orchestrate_the_fuller_tray_session_row - Orchestrate the fuller tray session row
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
- Summary: (unfilled: replace before this doc is used)
- Keywords: orchestrate, fuller, tray, session, row
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. 1. Trace a session from the provider usage payload through the tray contract, the menu model, Row, and the macOS cell, and confirm which windows each already carries.
- [ ] 2. 2. Carry freshness and reset into the drawn cell and re-lay the row so a second line holds them.
- [ ] 3. 3. Extend the snapshot with both windows as a minor-version addition, and keep the icon and ordering on the window that runs out first.
- [ ] 4. 4. Draw the second gauge, label both without relying on colour, and say both in the text rows.
- [ ] 5. 5. Add focused mapping and compatibility tests, then run the tray and project validation.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_093_draw_freshness_and_reset_on_the_macos_session_row`
- `item_094_publish_and_draw_both_limit_windows_per_session`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_093_draw_freshness_and_reset_on_the_macos_session_row`. Proof deferred to slice closeout.
- request-AC2 -> `item_093_draw_freshness_and_reset_on_the_macos_session_row`. Proof deferred to slice closeout.
- request-AC6 -> `item_093_draw_freshness_and_reset_on_the_macos_session_row`. Proof deferred to slice closeout.
- request-AC3 -> `item_094_publish_and_draw_both_limit_windows_per_session`. Proof deferred to slice closeout.
- request-AC4 -> `item_094_publish_and_draw_both_limit_windows_per_session`. Proof deferred to slice closeout.
- request-AC5 -> `item_094_publish_and_draw_both_limit_windows_per_session`. Proof deferred to slice closeout.
- request-AC7 -> `item_094_publish_and_draw_both_limit_windows_per_session`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_046_show_the_whole_session_row_on_macos_including_both_limit_windows`
- Product brief(s): `prod_033_a_tray_session_row_that_answers_before_it_is_clicked`
- Architecture decision(s): (none yet)
