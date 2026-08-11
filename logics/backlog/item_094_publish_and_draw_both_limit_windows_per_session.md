## item_094_publish_and_draw_both_limit_windows_per_session - Publish and draw both limit windows per session
> From version: 0.18.4
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Tray usability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: publish, draw, both, limit, windows, per, session
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- Both providers report a five-hour and a weekly window, and the tray contract keeps only one number, so a nearly spent week is invisible behind a five-hour window that just reset.
- One gauge cannot say which of two windows is the one about to run out.

# Scope
- In:
  - Extend the tray snapshot with both windows and their resets, as a minor-version addition.
  - Draw two gauges on the macOS row, each labelled with its window and distinguishable without colour.
  - Say both windows in the text rows on Windows and Linux.
  - Keep the icon state and the ordering following whichever window runs out first.
- Out:
  - Quota collection, provider probes, refresh cadence, or new windows beyond the two the providers publish.
  - A configurable layout or a chart.

# Acceptance criteria
- AC1: The snapshot carries both windows per session and an older companion renders exactly what it renders today.
- AC2: A session with two windows draws two labelled gauges; a session with one draws one and implies no missing second.
- AC3: The icon state and the menu ordering follow the window that runs out first.
- AC4: The text rows say both windows without becoming unreadable.
- AC5: Focused tests cover two windows, one window, neither, and the older-companion path.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: AC1: The snapshot carries both windows per session and an older companion renders exactly what it renders today.
- request-AC4 -> This backlog slice. Proof: AC2: A session with two windows draws two labelled gauges; a session with one draws one and implies no missing second.
- request-AC5 -> This backlog slice. Proof: AC3: The icon state and the menu ordering follow the window that runs out first.
- request-AC7 -> This backlog slice. Proof: AC4: The text rows say both windows without becoming unreadable.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_033_a_tray_session_row_that_answers_before_it_is_clicked`
- Architecture decision(s): (none yet)
- Request: `req_046_show_the_whole_session_row_on_macos_including_both_limit_windows`
- Primary task(s): `task_057_orchestrate_the_fuller_tray_session_row`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
