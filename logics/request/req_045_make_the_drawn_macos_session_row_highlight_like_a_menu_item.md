## req_045_make_the_drawn_macos_session_row_highlight_like_a_menu_item - Make the drawn macOS session row highlight like a menu item
> From version: 0.18.4
> Schema version: 1.0
> Status: Draft
> Understanding: 90
> Confidence: 85
> Complexity: Low
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: drawn, macos, session, row, highlight, like, menu, item
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Needs
- A session row on macOS is a drawn view, and a view-bearing NSMenuItem draws none of the standard furniture: no title, no state, no submenu arrow, and no highlight. The chevron is drawn now, so the row looks openable — but it stays visually inert under the pointer, which reads as a disabled row on a surface where every other item lights up.
- The cost is small and the surface is the one the user scans first, so a row that looks dead is a row people hesitate to click.

# Context
- task_054 drew the chevron and left the highlight, which adr_006 named as the other half of keeping the drawn cell.
- Highlighting needs more than the menu-open signal task_053 installs: per-item feedback comes from the NSMenuDelegate `menu:willHighlightItem:` callback, and the cell has to be able to redraw itself in two states.
- Since Big Sur the parent item's `highlighted` property stays true when the drawn row is no longer highlighted, so it cannot be the drawing signal.
- Only macOS is affected. Windows and Linux use text rows and get their platform's own highlight for free.

# Acceptance criteria
- AC1: A drawn session row under the pointer is visually highlighted the way an ordinary menu item is, and returns to normal when the pointer leaves.
- AC2: The highlight uses the system selection appearance, so it stays correct in both light and dark menu material and under accessibility contrast settings.
- AC3: The row's text and gauge remain legible against the highlighted background, including the coloured severity fill.
- AC4: Nothing else about the row changes: same identity binding, same chevron, same figures, same actions.
- AC5: Focused coverage or a recorded manual check on a real macOS host, since the highlight is drawing behaviour no headless test observes.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): `adr_006_tray_menu_lifecycle_observation_boundary`

# References
- `tray/src/mac_cell.rs`
- `tray/src/mac_menu_open.rs`
- `adr_006_tray_menu_lifecycle_observation_boundary`
- `task_054_orchestrate_actionable_and_truthful_cdx_tray_session_controls`

# Backlog
- `item_092_highlight_the_drawn_macos_session_row_on_hover`
