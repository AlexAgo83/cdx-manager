## item_175_remove_the_tray_from_cdx_manager_and_announce_contract_changes - Remove the tray from cdx-manager and announce contract changes
> From version: 0.27.12
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Low
> Theme: Tray companion
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-11-14 15:01:15

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: remove, tray, cdx, manager, announce, contract, changes
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- Every cdx release still rebuilds and waits for the tray.

# Scope
- In:
  - Delete tray/ and the tray asset workflow; drop the publish wait in the npm and PyPI workflows.
  - When a release bumps the tray schema major, notify cdx-tray (repository_dispatch).
  - Update the README table, docs and tray testing guide to point to cdx-tray.
- Out:
  - Rewriting earlier releases.

# Acceptance criteria
- AC4: a cdx release publishes without tray jobs, and earlier releases keep their assets.

# AC Traceability
- request-AC4 -> This backlog slice. Proof: AC4: a cdx release publishes without tray jobs, and earlier releases keep their assets.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_059_cdx_tray_the_tray_companion_released_on_its_own`
- Architecture decision(s): (none yet)
- Request: `req_085_move_the_tray_companion_into_its_own_cdx_tray_repository`
- Primary task(s): `task_089_orchestrate_the_cdx_tray_split`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.

# Executions
| When | Runner | Run id | Title | State | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- |
