## task_056_orchestrate_the_drawn_macos_row_highlight - Orchestrate the drawn macOS row highlight
> From version: 0.18.4
> Schema version: 1.0
> Status: Draft
> Understanding: 90
> Confidence: 85
> Progress: 0
> Complexity: Low
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

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
- [ ] 1. Extend the existing delegate with `menu:willHighlightItem:` and reach the drawn cell it names.
- [ ] 2. Give the cell a selected appearance from the system selection colour, and check the severity fill and every label stay legible over it in both materials.
- [ ] 3. Update affected Logics docs in the same wave and leave the repository commit-ready.
- [ ] 4. Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close a wave or step until the relevant automated tests and quality checks have been run successfully.

# Backlog
- `item_092_highlight_the_drawn_macos_session_row_on_hover`

# Definition of Done (DoD)
- [ ] Code is implemented and reviewed.
- [ ] Validation passes.
- [ ] Linked docs are synchronized.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: implementation delivers the bounded request need.
- request-AC2 -> This task. Proof: implementation scope is limited to the linked delivery slice.
- request-AC3 -> This task. Proof: implementation is executable from the promoted backlog item.
- backlog-AC1 -> This task. Proof: task remains bounded to the linked backlog scope.
- backlog-AC2 -> This task. Proof: task provides the executable implementation surface.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_045_make_the_drawn_macos_session_row_highlight_like_a_menu_item`
- Product brief(s): (none yet)
- Architecture decision(s): `adr_006_tray_menu_lifecycle_observation_boundary`
