## task_057_orchestrate_the_fuller_tray_session_row - Orchestrate the fuller tray session row
> From version: 0.18.4
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: corvus

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: orchestrate, fuller, tray, session, row
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. 1. Trace a session from the provider usage payload through the tray contract, the menu model, Row, and the macOS cell, and confirm which windows each already carries.
- [x] 2. 2. Carry freshness and reset into the drawn cell and re-lay the row so a second line holds them.
- [x] 3. 3. Extend the snapshot with both windows as a minor-version addition, and keep the icon and ordering on the window that runs out first.
- [x] 4. 4. Draw the second gauge, label both without relying on colour, and say both in the text rows.
- [x] 5. 5. Add focused mapping and compatibility tests, then run the tray and project validation.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_093_draw_freshness_and_reset_on_the_macos_session_row`
- `item_094_publish_and_draw_both_limit_windows_per_session`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: `row_detail` builds the second line from the same `freshness_words` the text rows use, so neither can describe a session the other would not. `the_drawn_row_says_how_old_the_figure_is_and_when_it_resets`, `a_current_figure_still_says_when_it_was_taken` and `the_drawn_row_names_the_states_a_refresh_cannot_fix` cover it; confirmed on screen by the operator (def1c09).
- request-AC2 -> This task. Proof: `reset_words` gives the distance when CDX computed one and the stamp only when it did not, shared with the text row. Covered by `an_absolute_reset_reaches_the_drawn_row_when_that_is_all_there_is` (def1c09).
- request-AC6 -> This task. Proof: the text rows gained the named windows and kept everything else; the drawn row keeps name, provider, figure, chevron and highlight, and now truncates with an ellipsis rather than clipping so a long name degrades legibly. 86 tray tests pass, including every pre-existing row test (a77a04e).
- request-AC3 -> This task. Proof: `menu_session` was already publishing `remaining_5h_pct` and `remaining_week_pct`; only the companion ignored them, so nothing about the payload changed and an older companion renders what it always did. Covered by `both_limit_windows_are_read_when_cdx_reports_them` and `a_session_without_windows_reads_as_having_none` (c6da6af).
- request-AC4 -> This task. Proof: each window gets its own line, its own bar and its own name, so they are told apart without colour; the five-hour bar is yellow and the week green for identity, with severity taking over below the icon's own thresholds. A single-window session draws one line and implies no missing second — `a_single_window_is_named_and_implies_no_missing_second`, `a_session_with_no_named_window_still_shows_its_figure` (c6da6af, 2d669d0).
- request-AC5 -> This task. Proof: the leading gauge, the icon state and the ordering all follow `available_pct`, which CDX computes as the minimum of the two windows, and `window_colour` reads its thresholds from the same `state_for` the glyph uses rather than restating them. Asserted in `both_windows_are_named_on_the_row`; the operator's screenshot showed the list ordered 59, 62, 65, 69, 79 by worst window (c6da6af, 2d669d0).
- request-AC7 -> This task. Proof: 86 tray tests and 855 Python tests pass; `cargo fmt --check` and `cargo clippy --all-targets` clean on aarch64-apple-darwin, x86_64-pc-windows-msvc and x86_64-unknown-linux-gnu. Three defects only a real menu could show were found and fixed this way: a row too narrow for what it now says, a figure column truncating a full week, and a badge the crate never cleared (a77a04e, 2d669d0, 6cfc900).

# Validation
- (no validation recorded yet)
- command: `cargo test (86 passed), cargo fmt --check, cargo clippy on the three targets, python3 -m pytest (855 passed), plus operator checks on a real macOS menu` | result: passed | date: 2026-08-11
- Finish workflow executed on 2026-08-11.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-11.
- Linked backlog item(s): `item_093_draw_freshness_and_reset_on_the_macos_session_row`, `item_094_publish_and_draw_both_limit_windows_per_session`
- Related request(s): `req_046_show_the_whole_session_row_on_macos_including_both_limit_windows`

# Links
- Request: `req_046_show_the_whole_session_row_on_macos_including_both_limit_windows`
- Product brief(s): `prod_033_a_tray_session_row_that_answers_before_it_is_clicked`
- Architecture decision(s): (none yet)
