## task_053_orchestrate_coherent_cdx_tray_alert_read_state - Orchestrate coherent CDX tray alert read state
> From version: 0.18.4
> Schema version: 1.0
> Status: Done
> Understanding: 96%
> Confidence: 92%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: corvus

# AI Context
- Summary: Orchestrate coherent CDX tray alert read state
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- adr_006 settles the observation boundary this task implements: menu opening is the only reading event, closing is not modelled on any platform, and an unavailable signal never clears.
- Nothing observes the menu today. Neither `muda::MenuEvent` nor `tray_icon::TrayIconEvent` carries an open edge, and the latter is not emitted on Linux at all, so each backend needs its own installation path.
- The three signals are `ksni::Tray::menu_about_to_show` on Linux, an NSMenuDelegate on `muda::ContextMenu::ns_menu()` on macOS, and a subclass on `TrayIcon::hwnd()` watching WM_INITMENUPOPUP on Windows.
- `muda` already installs MudaMenuDelegate on the macOS menu, so ours replaces it. It only carries a menu id for an API this companion never calls, but the coupling is deliberate and belongs in a test.
- TrackPopupMenu is modal, so the Windows pump in `tray/src/win.rs` is stopped for as long as the menu is open. That is why clearing is computed against the drawn snapshot rather than the arriving one.

# Plan
- [x] 1. Trace fresh event collection, spool acknowledgement, history merging, marker rendering, and the per-backend menu-open signal named in adr_006.
- [x] 2. Model the smallest volatile unread state with an explicit consultation boundary; prove that delivery acknowledgement and reading remain separate.
- [x] 3. Wire each backend's menu-open signal to the shared state against the drawn snapshot, retaining events that arrive while the menu is open and never clearing when the signal cannot be installed.
- [x] 4. Add focused state and backend regression tests, update concise tray behavior documentation, and run Rust, project, and Logics validation.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_089_unify_tray_alert_marker_and_recent_alert_read_state`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: `tray/src/unread.rs` holds the one state; `Render::next` records this poll's alerts into it and builds the menu from `unread.items()`, and the badge is `unread.marker()`. Covered by `the_marker_counts_exactly_what_the_menu_lists` (dea3d13).
- request-AC2 -> This task. Proof: `mark_drawn` captures the ids at every draw and `consulted` retains everything else, so the open menu keeps showing them and the next build does not. Covered by `a_consultation_clears_what_was_on_screen` and `a_second_consultation_without_a_redraw_clears_nothing_twice` (dea3d13).
- request-AC3 -> This task. Proof: clearing is measured against the drawn set, never the current list, so a later arrival is not in it. Covered by `an_alert_arriving_during_the_consultation_stays_unread`, which also asserts the badge stays lit (dea3d13).
- request-AC4 -> This task. Proof: `announce` still delivers then acknowledges through the spool, untouched; de-duplication by id moved into `Unread::record` with its crash-replay test intact (`a_redelivered_alert_is_not_listed_twice`), and the bound is the same `HISTORY_LIMIT`. The 793 Python tests covering CDX-side delivery and mute pass unchanged (dea3d13).
- request-AC5 -> This task. Proof: `menu_about_to_show` on Linux, an `NSMenuDelegate` on macOS, a `WM_INITMENUPOPUP` window-procedure subclass on Windows — each raising a flag the shared loop drains. Every backend gates clearing on its installation succeeding, and `without_a_consultation_nothing_is_ever_cleared` pins the failing-closed behaviour (dea3d13).
- request-AC6 -> This task. Proof: eight focused tests in `tray/src/unread.rs` cover the initial count, a consultation, a repeated consultation, post-open arrival, badge clearing, list clearing, redelivery, and the bound. `cargo test` 55 passed; clippy and `cargo check` clean on aarch64-apple-darwin, x86_64-pc-windows-msvc and x86_64-unknown-linux-gnu (dea3d13).

# Validation
- (no validation recorded yet)
- command: `cargo test (55 passed), cargo fmt --check, cargo clippy --all-targets on macOS/Windows/Linux targets, python3 -m pytest (793 passed)` | result: passed | date: 2026-08-11
- Finish workflow executed on 2026-08-11.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-11.
- Linked backlog item(s): `item_089_unify_tray_alert_marker_and_recent_alert_read_state`
- Related request(s): `req_042_synchronize_cdx_tray_alert_badges_with_menu_reading`

# Links
- Request: `req_042_synchronize_cdx_tray_alert_badges_with_menu_reading`
- Product brief(s): `prod_031_coherent_cdx_tray_unread_alerts`
- Architecture decision(s): `adr_006_tray_menu_lifecycle_observation_boundary`
