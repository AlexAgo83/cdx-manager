## req_049_open_a_tab_rather_than_a_window_where_the_platform_documents_one - Open a tab rather than a window where the platform documents one
> From version: 0.18.5
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Tray usability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-11 13:38:55

# AI Context
- Summary: Every session row opens a new terminal window, so three sessions cost three windows to arrange.
- Keywords: terminal tab, wt, gnome-terminal, konsole, macOS limitation
- Use when: Deciding how a tray session row opens a terminal.
- Skip when: Which terminal opens, which req_047 settled, or anything needing simulated keystrokes.

# Needs
- Every session row opens a new terminal window. Someone who opens three sessions in a row ends up with three windows to arrange, on top of the one they were already working in — and the row exists to save them a step, not to cost them a tidy-up.
- A tab is what a person opening a second session actually wants: the same window, one keystroke away from the first.

# Context
- req_047 made which terminal opens a preference. This is the other half of the same click and was deliberately left out of it, because choosing an application and choosing how it opens are separate decisions with separate platform stories.
- Windows Terminal documents `wt -w 0 nt`, which targets the existing window and opens a tab. gnome-terminal has `--tab` and konsole `--new-tab`. These are documented flags, and the same discipline as the terminal preference applies: honour what a platform states and fall back rather than guess.
- macOS is the awkward one. Terminal.app has no AppleScript verb for a new tab; the usual workaround drives System Events with a simulated Command-T, which needs the Accessibility permission and breaks when a dialog has focus. iTerm2 has its own dictionary. A conclusion of `window on macOS` may be the right answer, and it is one to write down rather than work around.
- Whatever is decided must not become a way to pass arbitrary flags: the same boundary as the terminal preference, where what is stored names a behaviour and never a command line.

# Acceptance criteria
- AC1: Where a terminal documents how to open a tab in an existing window, a session row uses it.
- AC2: Where it does not, the row opens a window as it does today, and the reason is documented rather than left as an inconsistency.
- AC3: A terminal that refuses the tab flag falls back to a window rather than leaving the click doing nothing.
- AC4: No new way to pass arbitrary flags or commands to a terminal comes with this.
- AC5: The behaviour is the same for Open session, Launch settings and the global status action, so a user does not learn two rules.
- AC6: Focused tests cover each platform's chosen invocation and its fallback; project validation passes.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_036_a_session_row_that_opens_where_you_already_are`
- Architecture decision(s): (none yet)

# References
- tray/src/mac.rs
- tray/src/linux.rs
- tray/src/win.rs
- req_047_let_the_operator_choose_which_terminal_the_tray_opens

# Backlog
- `item_097_open_a_tab_where_the_terminal_documents_how`
