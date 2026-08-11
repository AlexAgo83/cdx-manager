## task_060_orchestrate_tabs_instead_of_windows - Orchestrate tabs instead of windows
> From version: 0.18.5
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-11 13:47:58

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
- [ ] 1. 1. Establish what each platform actually documents, and settle the macOS conclusion in writing before implementing anything.
- [ ] 2. 2. Add the tab invocation per platform, keeping the window as the fallback.
- [ ] 3. 3. Apply it to every action that opens a terminal, so there is one rule.
- [ ] 4. 4. Add focused tests per platform and update the documentation with what is supported and what is not.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_097_open_a_tab_where_the_terminal_documents_how`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_097_open_a_tab_where_the_terminal_documents_how`. Proof deferred to slice closeout.
- request-AC2 -> `item_097_open_a_tab_where_the_terminal_documents_how`. Proof deferred to slice closeout.
- request-AC3 -> `item_097_open_a_tab_where_the_terminal_documents_how`. Proof deferred to slice closeout.
- request-AC4 -> `item_097_open_a_tab_where_the_terminal_documents_how`. Proof deferred to slice closeout.
- request-AC5 -> `item_097_open_a_tab_where_the_terminal_documents_how`. Proof deferred to slice closeout.
- request-AC6 -> `item_097_open_a_tab_where_the_terminal_documents_how`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_049_open_a_tab_rather_than_a_window_where_the_platform_documents_one`
- Product brief(s): `prod_036_a_session_row_that_opens_where_you_already_are`
- Architecture decision(s): (none yet)
