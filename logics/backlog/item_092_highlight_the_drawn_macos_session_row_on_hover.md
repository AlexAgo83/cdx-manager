## item_092_highlight_the_drawn_macos_session_row_on_hover - Highlight the drawn macOS session row on hover
> From version: 0.18.4
> Schema version: 1.0
> Status: Done
> Understanding: 90
> Confidence: 85
> Progress: 100%
> Complexity: Low
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: highlight, drawn, macos, session, row, hover
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- A view-bearing NSMenuItem draws no highlight, so the drawn session row stays inert under the pointer on a surface where every other item lights up.
- The parent item's `highlighted` property is unreliable since Big Sur, so the drawing signal has to come from the menu delegate rather than from the item.

# Scope
- In:
  - Extend the existing menu delegate with `menu:willHighlightItem:` and route it to the drawn cells.
  - Give the cell a selected appearance using the system selection colour, keeping text and gauge legible over it.
  - Record a manual check on a real macOS host, since no headless test observes drawing.
- Out:
  - Any change to row identity, actions, figures, chevron, or the other two backends.
  - Custom colours, animation, or a general-purpose menu-item view abstraction.

# Acceptance criteria
- AC1: The row under the pointer is highlighted with the system selection appearance and returns to normal when the pointer leaves.
- AC2: Text, provider, figure, chevron and the severity fill stay legible over the highlight in both light and dark menu material.
- AC3: Row identity, actions and layout are unchanged, and the other backends are untouched.
- AC4: A manual macOS check is recorded, since the behaviour is drawing no headless test observes.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: The row under the pointer is highlighted with the system selection appearance and returns to normal when the pointer leaves.
- request-AC2 -> This backlog slice. Proof: AC2: Text, provider, figure, chevron and the severity fill stay legible over the highlight in both light and dark menu material.
- request-AC3 -> This backlog slice. Proof: AC2: Text, provider, figure, chevron and the severity fill stay legible over the highlight in both light and dark menu material.
- request-AC4 -> This backlog slice. Proof: AC3: Row identity, actions and layout are unchanged, and the other backends are untouched.
- request-AC5 -> This backlog slice. Proof: AC4: A manual macOS check is recorded, since the behaviour is drawing no headless test observes.

# Decision framing
- Product framing: Not needed
- Architecture framing: Follows `adr_006_tray_menu_lifecycle_observation_boundary`, which keeps the drawn cell and therefore owes it the furniture AppKit no longer draws.

# Links
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
- Request: `req_045_make_the_drawn_macos_session_row_highlight_like_a_menu_item`
- Primary task(s): `task_056_orchestrate_the_drawn_macos_row_highlight`

# Priority
- Priority: Low
- Rationale: Cosmetic on one platform; the row is already readable and clickable, and the chevron already says it opens.

# Notes
- Split out of task_054, which drew the chevron and left the highlight.
- Task `task_056_orchestrate_the_drawn_macos_row_highlight` was finished via `logics-manager flow finish task` on 2026-08-11.

# Tasks
- `task_056_orchestrate_the_drawn_macos_row_highlight`
