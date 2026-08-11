## task_060_orchestrate_tabs_instead_of_windows - Orchestrate tabs instead of windows
> From version: 0.18.5
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 90%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-11 13:47:58
> Owner: Codex

# AI Context
- Summary: Settle what macOS can actually do before implementing, then add the documented tab flags with a window fallback.
- Keywords: terminal tab, per-platform invocation, fallback, macOS limitation
- Use when: Implementing req_049. Lowest priority of the open work.
- Skip when: Anything requiring Accessibility permissions or simulated input.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- Where terminals are opened today: `open_terminal_in` in `tray/src/mac.rs`, `tray/src/linux.rs` and `tray/src/win.rs`. `req_047` already made *which* terminal a preference; this decides *how* it opens, and the two compose at the same call sites.
- What each platform documents: Windows Terminal has `wt -w 0 nt`, which targets the existing window and opens a tab; gnome-terminal has `--tab`; konsole has `--new-tab`. These are the ones that can be honoured without guessing, which is the same discipline `req_047` applied to `wt`.
- SETTLED after research: opening a tab is a property of the terminal, not of the platform. macOS is not the exception — Terminal.app is. Since `req_047` already records which terminal the operator chose, the mechanism follows from that choice rather than from the operating system.
- What each documents: iTerm2 has `create tab with default profile command "..."` in a mature AppleScript dictionary; WezTerm has `wezterm cli spawn`, which spawns into the window of the current pane, plus `wezterm start --new-tab`; kitty has `kitty @ launch --type=tab`, but only when the operator has enabled `allow_remote_control` in their own config, so it is a try-and-fall-back rather than a guarantee; Windows Terminal has `wt -w 0 nt`; gnome-terminal has `--tab` and konsole `--new-tab`.
- What documents nothing: Terminal.app has no AppleScript verb for a new tab, Ghostty has no CLI for it (an open request, ghostty-org/ghostty#12136), and Alacritty has no tabs at all by design. These open a window, and the documentation says so as a conclusion rather than leaving it looking like an oversight.
- Ruled out: driving System Events with a simulated Command-T. It needs the Accessibility permission — which a tray would have to ask an operator to grant — and it breaks whenever a dialog has focus.
- Lowest priority of the open work: nothing is broken, and three windows to arrange is a cost rather than a failure.

# Plan
- [x] 1. 1. Establish what each platform actually documents, and settle the macOS conclusion in writing before implementing anything.
- [x] 2. 2. Add the tab invocation per platform, keeping the window as the fallback.
- [x] 3. 3. Apply it to every action that opens a terminal, so there is one rule.
- [x] 4. 4. Add focused tests per platform and update the documentation with what is supported and what is not.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_097_open_a_tab_where_the_terminal_documents_how`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: Windows Terminal receives `-w 0 nt` in `93b806d`.
- request-AC2 -> This task. Proof: gnome-terminal and konsole receive their documented tab flags.
- request-AC3 -> This task. Proof: unsupported terminals retain the existing window fallback.
- request-AC4 -> This task. Proof: every menu action routes through the shared opener.
- request-AC5 -> This task. Proof: no simulated input or Accessibility path was added.
- request-AC6 -> This task. Proof: `cargo check --manifest-path tray/Cargo.toml` passed for `93b806d`.

# Validation
- (no validation recorded yet)
- command: `cargo check --manifest-path tray/Cargo.toml` | result: passed | date: 2026-08-11
- Finish workflow executed on 2026-08-11.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-11.
- Linked backlog item(s): `item_097_open_a_tab_where_the_terminal_documents_how`
- Related request(s): `req_049_open_a_tab_rather_than_a_window_where_the_platform_documents_one`

# Links
- Request: `req_049_open_a_tab_rather_than_a_window_where_the_platform_documents_one`
- Product brief(s): `prod_036_a_session_row_that_opens_where_you_already_are`
- Architecture decision(s): (none yet)
