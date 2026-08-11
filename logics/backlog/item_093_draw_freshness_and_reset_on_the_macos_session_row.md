## item_093_draw_freshness_and_reset_on_the_macos_session_row - Draw freshness and reset on the macOS session row
> From version: 0.18.4
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 45%
> Complexity: Low
> Theme: Tray usability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: draw, freshness, reset, macos, session, row
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- The drawn cell replaces the menu item's label, and was never given the freshness and reset the label carried.
- A percentage with no age cannot be acted on, and the reset is what tells a user whether to wait or to switch.

# Scope
- In:
  - Carry updated_ago, freshness and reset through Row into the macOS cell.
  - Lay the row out so a second line can carry them without crowding the first.
  - Keep the auth-locked and never-reported wording the text rows already use.
- Out:
  - The second limit window, which is its own slice.
  - Any change to the text rows or to the other backends.

# Acceptance criteria
- AC1: The drawn row states the age of its figure, and says running or never reported where the text row does.
- AC2: The drawn row states the reset as a distance when CDX computed one, and as a stamp only when it did not.
- AC3: Nothing already on the row is lost or displaced, including the chevron and the highlight.
- AC4: Focused tests cover the mapping into the cell for fresh, stale, auth-locked and never-reported sessions.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: The drawn row states the age of its figure, and says running or never reported where the text row does.
- request-AC2 -> This backlog slice. Proof: AC2: The drawn row states the reset as a distance when CDX computed one, and as a stamp only when it did not.
- request-AC6 -> This backlog slice. Proof: AC3: Nothing already on the row is lost or displaced, including the chevron and the highlight.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_033_a_tray_session_row_that_answers_before_it_is_clicked`
- Architecture decision(s): (none yet)
- Request: `req_046_show_the_whole_session_row_on_macos_including_both_limit_windows`
- Primary task(s): `task_057_orchestrate_the_fuller_tray_session_row`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
