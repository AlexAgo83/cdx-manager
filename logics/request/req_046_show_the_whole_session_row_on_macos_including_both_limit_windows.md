## req_046_show_the_whole_session_row_on_macos_including_both_limit_windows - Show the whole session row on macOS, including both limit windows
> From version: 0.18.4
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Tray usability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: show, whole, session, row, macos, including, both, limit, windows
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Needs
- A macOS session row no longer says how old its figure is, nor when the limit resets. The text rows on Windows and Linux say both; the drawn macOS cell replaces the label entirely and was only ever given the name, the provider, the gauge and the figure, so the two facts a user checks before deciding whether to trust a percentage are simply absent on the platform that draws.
- A percentage with no age is a percentage nobody can act on: a figure from three hours ago and one from thirty seconds ago read identically, and only one of them is a reason to switch accounts.
- Both providers publish two limit windows — a five-hour one and a weekly one — and the tray shows a single number. The one that matters is whichever runs out first, and a user cannot tell which that is from one bar. A week that is nearly spent is invisible behind a five-hour window that just reset.

# Context
- src/claude_usage.py and src/codex_usage.py already produce remaining_5h_pct, remaining_week_pct, reset_5h_at and reset_week_at. The tray contract publishes only available_pct and one reset, so the second window is lost in CDX rather than missing from the providers.
- menu_session in src/tray_contract.py already publishes updated_ago and reset_in, and the text row in tray/src/menu.rs renders both. Only the drawn cell drops them.
- adr_006 records why the drawn cell is kept and what it costs: an NSMenuItem carrying a view draws none of its own furniture, so anything the row should say has to be drawn deliberately. This is the third thing found missing that way, after the provider and the submenu chevron.
- The row is 260 by 20 points and already carries a name, a provider, a gauge, a figure and a chevron. Two more facts and a second gauge do not fit on one line.

# Acceptance criteria
- AC1: A macOS session row states how old its figure is, in the same words the text rows use, and says so distinctly when a session has never reported or is holding the auth lock.
- AC2: A macOS session row states when the limit resets whenever CDX knows, using the distance when it has one and the stamp only when it does not.
- AC3: The snapshot carries both limit windows per session, and a companion older than that change keeps rendering exactly what it renders today.
- AC4: A session with two windows draws two gauges, distinguishable without colour, each labelled with the window it measures; a session with one window draws one and does not imply a missing second.
- AC5: The icon state and the menu ordering keep following the window that runs out first, so the glyph and the row cannot disagree about which session is the constrained one.
- AC6: The text rows on Windows and Linux keep saying everything the drawn row says, and no row loses the name, provider, figure, freshness, reset or chevron it has today.
- AC7: Focused tests cover the mapping of both windows, the single-window case, the never-reported case, and the unchanged behaviour of an older companion; the tray and project validation pass.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_033_a_tray_session_row_that_answers_before_it_is_clicked`
- Architecture decision(s): (none yet)

# References
- tray/src/mac_cell.rs
- tray/src/runner.rs
- src/tray_contract.py
- src/claude_usage.py
- src/codex_usage.py
- adr_006_tray_menu_lifecycle_observation_boundary

# Backlog
- `item_093_draw_freshness_and_reset_on_the_macos_session_row`
- `item_094_publish_and_draw_both_limit_windows_per_session`
