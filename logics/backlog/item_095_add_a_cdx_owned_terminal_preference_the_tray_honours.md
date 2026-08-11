## item_095_add_a_cdx_owned_terminal_preference_the_tray_honours - Add a CDX-owned terminal preference the tray honours
> From version: 0.18.4
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Tray usability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: add, cdx, owned, terminal, preference, tray, honours
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- The terminal is chosen by the companion, per platform, with no way for the operator to say otherwise.
- Any fix has to avoid turning a stored preference into a command the companion runs.

# Scope
- In:
  - A cdx command to set, show and clear a preferred terminal application.
  - Validation restricting the value to an application name or bundle identifier, never a command line.
  - Carrying it in the tray snapshot and honouring it on macOS through open -a, on Linux by preferring the named emulator before the existing list, and on Windows through the existing routing.
  - Falling back to today's behaviour when the named application is absent or fails.
  - Documentation of the setting and of what it deliberately cannot express.
- Out:
  - Per-session terminals, terminal profiles, or launch flags.
  - Detecting the current terminal, or changing what runs inside it.

# Acceptance criteria
- AC1: Setting, showing and clearing the preference works and is reversible.
- AC2: A value that is not an application name is refused with the reason, and never stored.
- AC3: Each platform honours the preference the way it launches applications, and falls back to today's behaviour when it cannot.
- AC4: The companion reads it from the snapshot and keeps no store of its own.
- AC5: Focused tests cover default, named, absent and refused values.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Setting, showing and clearing the preference works and is reversible.
- request-AC2 -> This backlog slice. Proof: AC2: A value that is not an application name is refused with the reason, and never stored.
- request-AC3 -> This backlog slice. Proof: AC3: Each platform honours the preference the way it launches applications, and falls back to today's behaviour when it cannot.
- request-AC4 -> This backlog slice. Proof: AC4: The companion reads it from the snapshot and keeps no store of its own.
- request-AC5 -> This backlog slice. Proof: AC5: Focused tests cover default, named, absent and refused values.
- request-AC6 -> This backlog slice. Proof: AC5: Focused tests cover default, named, absent and refused values.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_034_the_tray_opens_the_terminal_you_actually_use`
- Architecture decision(s): (none yet)
- Request: `req_047_let_the_operator_choose_which_terminal_the_tray_opens`
- Primary task(s): `task_058_orchestrate_the_preferred_tray_terminal`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.

# Tasks
- `task_058_orchestrate_the_preferred_tray_terminal`

# Notes
- Task `task_058_orchestrate_the_preferred_tray_terminal` was finished via `logics-manager flow finish task` on 2026-08-11.
