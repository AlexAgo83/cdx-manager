## item_098_name_the_prefix_an_install_or_update_acted_on - Name the prefix an install or update acted on
> From version: 0.18.5
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 90%
> Complexity: Low
> Theme: Diagnostics
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-11 13:38:56

# AI Context
- Summary: Install, update and uninstall report the prefix they acted on, and say when it is a session profile rather than the operator's own home.
- Keywords: cdx update, install prefix, session profile, JSON result
- Use when: Implementing the install-side half of req_050.
- Skip when: The companion and hook diagnostics, which are the other slice.

# Problem
- `cdx update` inside a session updates the session's copy and reports plain success, so the operator's own installation silently stays behind.
- The prefix is known at the moment of acting and is never said.

# Scope
- In:
  - Report the prefix in the text and JSON results of install, update and uninstall paths.
  - Detect that the home is a cdx session profile and say so, naming both homes.
  - Keep an ordinary run's output unchanged.
- Out:
  - Refusing to act, choosing a different home, or changing resolution rules.
  - Any change to what is installed or how.

# Acceptance criteria
- AC1: The prefix acted on appears in both output modes.
- AC2: Acting inside a session profile is stated, with both homes named.
- AC3: A normal run from a normal shell gains no extra line.
- AC4: Focused tests cover the redirected and ordinary cases.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: The prefix acted on appears in both output modes.
- request-AC2 -> This backlog slice. Proof: AC2: Acting inside a session profile is stated, with both homes named.
- request-AC4 -> This backlog slice. Proof: AC3: A normal run from a normal shell gains no extra line.
- request-AC5 -> This backlog slice. Proof: AC4: Focused tests cover the redirected and ordinary cases.
- request-AC6 -> This backlog slice. Proof: AC4: Focused tests cover the redirected and ordinary cases.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_037_commands_that_name_what_they_are_about_to_touch`
- Architecture decision(s): (none yet)
- Request: `req_050_say_which_installation_and_which_home_a_command_is_acting_on`
- Primary task(s): `task_061_orchestrate_commands_that_name_what_they_touch`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
