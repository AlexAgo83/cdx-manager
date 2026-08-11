## task_054_orchestrate_actionable_and_truthful_cdx_tray_session_controls - Orchestrate actionable and truthful CDX tray session controls
> From version: 0.18.4
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 90%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: corvus

# AI Context
- Summary: Orchestrate actionable and truthful CDX tray session controls
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- Blocked on task_051: it replaces the positional `ActionId::Session(index)` with a stable session identifier, and this task binds every row action to that identity. Starting first would bind actions to a rank task_051 makes volatile.
- An `NSMenuItem` carrying a view draws none of the standard furniture — no title, no state, no highlight, and no submenu chevron — and session rows are already drawn cells (`backend.rs:113` -> `mac_cell::Cell`). A row that gains a submenu therefore shows nothing indicating it can be opened.
- adr_006 keeps the drawn cell and makes the chevron and the highlight part of it. The highlight is driven by the same menu-open signal task_053 installs, so the two tasks share that plumbing.
- Since Big Sur the parent item's highlighted property stays true when the drawn row is no longer visually highlighted, so it cannot be the drawing signal.

# Plan
- [x] 1. Trace a session row from the capacity-sorted snapshot through the shared menu model, macOS custom cell, each native backend, and native/WSL terminal routing.
- [x] 2. Define the smallest declarative session-action contract and submenu representation, bound to the stable session identity from task_051, without turning the tray into a configuration editor.
- [x] 3. Implement explicit open and configuration-view actions, capability-gated extension routing, and clear next-launch wording while preserving the existing global actions and alert behaviour; draw the submenu chevron and the highlight inside the macOS cell.
- [x] 4. Add focused identity, action-routing, unavailable-capability, and platform fallback tests; validate the tray and CDX command paths, then record the interaction boundary for the later Logics plugin work.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_090_add_an_explicit_capability_safe_action_submenu_to_every_tray_session_row`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: each row is an `Entry::Submenu` whose `about` is `ActionId::Session(name)`; `rows_for` binds the drawn macOS cell through that same name. `a_session_overtaking_another_still_opens_the_row_that_was_clicked` reorders providers and asserts the row, its label and every action inside name one session (9bd5b28).
- request-AC2 -> This task. Proof: `session_actions` declares Open session and Launch settings; the macOS loop routes `SessionConfig` to `cdx config <name>` through `open_terminal`, and the Windows loop through the same `open_terminal(&transport, ...)` the status command uses, so the WSL path is the existing one. Covered by `a_session_row_offers_opening_and_its_next_launch_settings` (9bd5b28).
- request-AC3 -> This task. Proof: the only settings surface is a view of `cdx config`, labelled `Launch settings (next launch)` and asserted by `the_settings_action_says_it_applies_to_the_next_launch`. Nothing in the tray writes a setting, stops or restarts a provider process (9bd5b28).
- request-AC4 -> This task. Proof: actions are a declared `Vec<SessionAction>` rather than inline entries, so an extension is another declared item; `no_empty_extension_placeholder_is_rendered` asserts no Extensions or Logics heading exists while nothing declares one (9bd5b28).
- request-AC5 -> This task. Proof: `Availability::Unavailable(reason)` renders a disabled row carrying the reason, pinned by `an_unavailable_action_is_disabled_and_carries_its_reason`. Every action id carries its own session name, so no action can reach a different session, and none of them runs an arbitrary command (9bd5b28).
- request-AC6 -> This task. Proof: 59 tray tests, including the four added here plus the identity and ordering tests from task_051 and the existing gauge, freshness, reset, alert, refresh and quit coverage. `cargo fmt --check` and `cargo clippy --all-targets` clean on aarch64-apple-darwin, x86_64-pc-windows-msvc and x86_64-unknown-linux-gnu; Python suite 793 passed (9bd5b28).

# Validation
- (no validation recorded yet)
- command: `cargo test (59 passed), cargo fmt --check, cargo clippy --all-targets on the macOS/Windows/Linux targets, python3 -m pytest (793 passed)` | result: passed | date: 2026-08-11
- Finish workflow executed on 2026-08-11.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-11.
- Linked backlog item(s): `item_090_add_an_explicit_capability_safe_action_submenu_to_every_tray_session_row`
- Related request(s): `req_043_make_cdx_tray_session_rows_actionable_without_misleading_live_settings`

# Links
- Request: `req_043_make_cdx_tray_session_rows_actionable_without_misleading_live_settings`
- Product brief(s): `prod_032_actionable_cdx_tray_session_controls`
- Architecture decision(s): `adr_006_tray_menu_lifecycle_observation_boundary`
