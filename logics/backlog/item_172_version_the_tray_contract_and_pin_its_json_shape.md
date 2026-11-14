## item_172_version_the_tray_contract_and_pin_its_json_shape - Version the tray contract and pin its JSON shape
> From version: 0.27.12
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Low
> Theme: Tray companion
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-11-14 15:01:07

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: version, tray, contract, pin, json, shape
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- The tray depends on `cdx tray status --json` but nothing marks a breaking change of that output.

# Scope
- In:
  - Reuse the existing `schema` {name, major, minor} of the tray snapshot (1.3 today); a major bump is the breaking change.
  - A test pins the shape (keys and types) and fails on change unless the contract version is bumped in the same change.
- Out:
  - Moving files.

# Acceptance criteria
- AC1: the field exists and the shape test guards it.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: the field exists and the shape test guards it.

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
