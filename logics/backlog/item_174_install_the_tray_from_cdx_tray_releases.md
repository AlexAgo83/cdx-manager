## item_174_install_the_tray_from_cdx_tray_releases - Install the tray from cdx-tray releases
> From version: 0.27.12
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Tray companion
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-11-14 15:01:08

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: install, tray, cdx, releases
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- `cdx tray install` only knows the cdx release of the same version.

# Scope
- In:
  - Pick the newest cdx-tray release whose supported contract range includes the installed cdx schema major; verify against its ledger; refuse otherwise with an update message.
  - Keep installing from the matching cdx-manager release for versions published before the move.
- Out:
  - Autostart and shortcut behaviour changes.

# Acceptance criteria
- AC3: install picks a compatible cdx-tray release and refuses an incompatible one.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: AC3: install picks a compatible cdx-tray release and refuses an incompatible one.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_059_cdx_tray_the_tray_companion_released_on_its_own`
- Architecture decision(s): (none yet)
- Request: `req_085_move_the_tray_companion_into_its_own_cdx_tray_repository`
- Primary task(s): `task_089_orchestrate_the_cdx_tray_split`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.

# Executions
| When | Runner | Run id | Title | State | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- |
