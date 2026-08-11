## task_056_orchestrate_the_drawn_macos_row_highlight - Orchestrate the drawn macOS row highlight
> From version: 0.18.4
> Schema version: 1.0
> Status: Done
> Understanding: 95
> Confidence: 80
> Progress: 100%
> Complexity: Low
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: corvus

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: orchestrate, drawn, macos, row, highlight
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Context
- Execute the bounded delivery slice split out of task_054, which drew the chevron and left the highlight.
- The signal is `menu:willHighlightItem:` on the delegate `tray/src/mac_menu_open.rs` already installs; the menu-open signal alone cannot say which row the pointer is on.
- The item's own `highlighted` property is unreliable since Big Sur and must not be the drawing signal.
- Needs a real macOS host to confirm: this is drawing behaviour, and no headless test observes it.

# Plan
- [x] 1. Extend the existing delegate with `menu:willHighlightItem:` and reach the drawn cell it names.
- [x] 2. Give the cell a selected appearance from the system selection colour, and check the severity fill and every label stay legible over it in both materials.
- [x] 3. Update affected Logics docs in the same wave and leave the repository commit-ready.
- [x] 4. Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close a wave or step until the relevant automated tests and quality checks have been run successfully.

# Backlog
- `item_092_highlight_the_drawn_macos_session_row_on_hover`

# Definition of Done (DoD)
- [x] Code is implemented and reviewed.
- [x] Validation passes.
- [x] Linked docs are synchronized.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: the row is an NSView subclass drawing its selection when `menu:willHighlightItem:` names it, and clearing when the pointer leaves — `item` is None there. Confirmed visually on a real macOS session by the operator (c6ebf45).
- request-AC2 -> This task. Proof: `unemphasizedSelectedContentBackgroundColor` is the system pair AppKit keeps legible against ordinary label colours in both menu materials, so no label is repainted and neither theme needs tuning (c6ebf45).
- request-AC3 -> This task. Proof: only the background is drawn, under the existing labels, gauge and chevron; the operator's check covered legibility over the highlight (c6ebf45).
- request-AC4 -> This task. Proof: identity, actions and layout are untouched — the only change to `build_cell` is the container class. Windows and Linux use text rows and were not compiled against differently: clippy clean on all three targets (c6ebf45).
- request-AC5 -> This task. Proof: recorded in `# Validation` — the manual macOS check was held open until it had actually been done, then written down as done rather than assumed (c6ebf45).
- backlog-AC1 -> This task. Proof: task remains bounded to the linked backlog scope.
- backlog-AC2 -> This task. Proof: task provides the executable implementation surface.

# Validation
- cargo test (77 passed), cargo fmt --check, cargo clippy --all-targets clean on aarch64-apple-darwin, x86_64-pc-windows-msvc and x86_64-unknown-linux-gnu (c6ebf45).
- Manual check on a real macOS session, performed by the operator: the drawn row lights up under the pointer. That is the part no headless test can observe, and it is why it was held open until someone had looked.
- command: `cargo test (77 passed), cargo fmt --check, cargo clippy on the three targets, plus an operator visual check on macOS` | result: passed | date: 2026-08-11
- Finish workflow executed on 2026-08-11.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-11.
- Linked backlog item(s): `item_092_highlight_the_drawn_macos_session_row_on_hover`
- Related request(s): `req_045_make_the_drawn_macos_session_row_highlight_like_a_menu_item`

# Links
- Request: `req_045_make_the_drawn_macos_session_row_highlight_like_a_menu_item`
- Product brief(s): (none yet)
- Architecture decision(s): `adr_006_tray_menu_lifecycle_observation_boundary`
