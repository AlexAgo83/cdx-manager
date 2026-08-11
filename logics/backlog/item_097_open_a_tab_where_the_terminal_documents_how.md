## item_097_open_a_tab_where_the_terminal_documents_how - Open a tab where the terminal documents how
> From version: 0.18.5
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Tray usability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-11 13:38:56

# AI Context
- Summary: Use each terminal's own documented tab flag, fall back to a window, and write down the macOS conclusion.
- Keywords: wt -w 0 nt, gnome-terminal --tab, konsole --new-tab, fallback
- Use when: Implementing req_049.
- Skip when: Adding operator-supplied terminal flags, profiles or working directories.

# Problem
- Three sessions opened from the tray are three windows to arrange.
- The mechanisms differ per platform and one of them does not exist, so a single implementation would either guess or simulate input.

# Scope
- In:
  - Use `wt -w 0 nt` on Windows Terminal, `--tab` on gnome-terminal and `--new-tab` on konsole.
  - Fall back to a window whenever the flag is refused or unknown.
  - Document the macOS conclusion, whatever it turns out to be.
  - Apply the same behaviour to every action that opens a terminal.
- Out:
  - Simulated keystrokes or Accessibility-dependent automation.
  - Any new operator-supplied flag, profile or command.

# Acceptance criteria
- AC1: Each supported terminal opens a tab through its own documented flag.
- AC2: An unsupported terminal opens a window, and the documentation says which are which.
- AC3: A refused flag falls back to a window in the same click.
- AC4: Every terminal-opening action behaves identically.
- AC5: Focused tests cover the supported, unsupported and refused cases.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Each supported terminal opens a tab through its own documented flag.
- request-AC2 -> This backlog slice. Proof: AC2: An unsupported terminal opens a window, and the documentation says which are which.
- request-AC3 -> This backlog slice. Proof: AC3: A refused flag falls back to a window in the same click.
- request-AC4 -> This backlog slice. Proof: AC4: Every terminal-opening action behaves identically.
- request-AC5 -> This backlog slice. Proof: AC5: Focused tests cover the supported, unsupported and refused cases.
- request-AC6 -> This backlog slice. Proof: AC5: Focused tests cover the supported, unsupported and refused cases.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_036_a_session_row_that_opens_where_you_already_are`
- Architecture decision(s): (none yet)
- Request: `req_049_open_a_tab_rather_than_a_window_where_the_platform_documents_one`
- Primary task(s): `task_060_orchestrate_tabs_instead_of_windows`

# Priority
- Priority: Low
- Rationale: Set by scaffold input or defaulted for grooming.
