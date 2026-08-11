## item_099_report_the_cdx_and_store_the_companion_actually_reaches - Report the CDX and store the companion actually reaches
> From version: 0.18.5
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Diagnostics
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-11 13:38:56

# AI Context
- Summary: cdx tray doctor reports the cdx the companion resolves and the store a hook would publish into, and names a mismatch.
- Keywords: tray doctor, WSL transport, CDX_TRAY_CDX, heartbeat store
- Use when: Implementing the diagnostics half of req_050.
- Skip when: The install and update reporting, which is the other slice.

# Problem
- A companion resolves cdx through a non-login PATH, or across WSL, and can reach a different installation than the operator's terminal — with nothing able to see both sides at once.
- A hook publishes into whatever CDX_HOME it inherited, so a tray can be running and listening to a different store.

# Scope
- In:
  - Have `cdx tray doctor` report the command the companion resolves and its version, including through the WSL transport.
  - Report the store the hook would publish into and whether a live heartbeat is there.
  - Name the mismatch plainly when the two differ.
- Out:
  - Changing PATH or CDX_HOME resolution, or repairing a mismatch automatically.
  - New commands beyond the existing doctor.

# Acceptance criteria
- AC1: Doctor names the cdx the companion resolves and its version, natively and across WSL.
- AC2: Doctor names the store a hook would publish into and whether a companion is beating there.
- AC3: A mismatch between them is stated, with what to set to fix it.
- AC4: Focused tests cover matching and mismatching cases on both transports.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: AC1: Doctor names the cdx the companion resolves and its version, natively and across WSL.
- request-AC4 -> This backlog slice. Proof: AC2: Doctor names the store a hook would publish into and whether a companion is beating there.
- request-AC5 -> This backlog slice. Proof: AC3: A mismatch between them is stated, with what to set to fix it.
- request-AC6 -> This backlog slice. Proof: AC4: Focused tests cover matching and mismatching cases on both transports.

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
