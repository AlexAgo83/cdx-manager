## item_173_create_the_public_cdx_tray_repository_with_its_ci_and_releases - Create the public cdx-tray repository with its CI and releases
> From version: 0.27.12
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Tray companion
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-11-14 15:01:07

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: create, public, cdx, tray, repository, releases
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- The tray has no home of its own.

# Scope
- In:
  - Clean copy of tray/ (no history), licence, README in the shared short shape, CI building and testing on its own changes.
  - Release workflow: one asset per OS and architecture plus a checksum ledger, triggered by a tray tag or by a cdx contract announcement (repository_dispatch).
  - The tray keeps its existing update hint for an unknown schema major.
  - Privacy scan of every file and commit before the first push.
- Out:
  - New tray features.

# Acceptance criteria
- AC2: a cdx-tray release publishes every asset with its ledger.
- AC5: an unknown contract shows an update message.

# AC Traceability
- request-AC2 -> This backlog slice. Proof: AC2: a cdx-tray release publishes every asset with its ledger.
- request-AC5 -> This backlog slice. Proof: AC5: an unknown contract shows an update message.

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
