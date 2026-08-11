## task_053_orchestrate_coherent_cdx_tray_alert_read_state - Orchestrate coherent CDX tray alert read state
> From version: 0.18.4
> Schema version: 1.0
> Status: Ready
> Understanding: 96%
> Confidence: 92%
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
- adr_006 settles the observation boundary this task implements: menu opening is the only reading event, closing is not modelled on any platform, and an unavailable signal never clears.
- Nothing observes the menu today. Neither `muda::MenuEvent` nor `tray_icon::TrayIconEvent` carries an open edge, and the latter is not emitted on Linux at all, so each backend needs its own installation path.
- The three signals are `ksni::Tray::menu_about_to_show` on Linux, an NSMenuDelegate on `muda::ContextMenu::ns_menu()` on macOS, and a subclass on `TrayIcon::hwnd()` watching WM_INITMENUPOPUP on Windows.
- `muda` already installs MudaMenuDelegate on the macOS menu, so ours replaces it. It only carries a menu id for an API this companion never calls, but the coupling is deliberate and belongs in a test.
- TrackPopupMenu is modal, so the Windows pump in `tray/src/win.rs` is stopped for as long as the menu is open. That is why clearing is computed against the drawn snapshot rather than the arriving one.

# Plan
- [ ] 1. Trace fresh event collection, spool acknowledgement, history merging, marker rendering, and the per-backend menu-open signal named in adr_006.
- [ ] 2. Model the smallest volatile unread state with an explicit consultation boundary; prove that delivery acknowledgement and reading remain separate.
- [ ] 3. Wire each backend's menu-open signal to the shared state against the drawn snapshot, retaining events that arrive while the menu is open and never clearing when the signal cannot be installed.
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
- Architecture decision(s): `adr_006_tray_menu_lifecycle_observation_boundary`
