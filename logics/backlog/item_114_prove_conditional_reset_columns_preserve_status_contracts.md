## item_114_prove_conditional_reset_columns_preserve_status_contracts - Prove conditional reset columns preserve status contracts
> From version: 0.18.6
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 90%
> Progress: 100%
> Complexity: Low
> Theme: Status regression safety
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Prove conditional terminal-table columns do not change status data, detail, or ranking behavior.
- Keywords: prove, conditional, reset, columns, preserve, status, contracts
- Use when: Adding focused status-table regression coverage for reset visibility.
- Skip when: Changing the reset visibility calculation itself.

# Problem
- Reset data also informs detail and recommendation paths. A display cleanup must not accidentally make a known reset unavailable to ranking or JSON consumers.

# Scope
- In:
  - Add focused rendering tests for absence, independent presence, zero counts, disabled rows, and compact output.
  - Retain existing detail, JSON, and recommendation coverage and update concise user documentation only if it asserts fixed columns.
- Out:
  - Changing the JSON contract, the reset countdown formatter, provider probes, or selector ranking.

# Acceptance criteria
- AC1: JSON and detailed reset fields remain present independently of table visibility.
- AC2: Existing reset-based recommendation tests stay green.
- AC3: Project and Logics validation pass.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: AC1: JSON and detailed reset fields remain present independently of table visibility.
- request-AC4 -> This backlog slice. Proof: AC2: Existing reset-based recommendation tests stay green.
- request-AC5 -> This backlog slice. Proof: AC3: Project and Logics validation pass.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_044_signal_only_cdx_status_reset_columns`
- Architecture decision(s): (none yet)
- Request: `req_057_hide_empty_reset_columns_from_cdx_status`
- Primary task(s): `task_068_orchestrate_conditional_reset_columns_in_cdx_status`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.

# Tasks
- `task_068_orchestrate_conditional_reset_columns_in_cdx_status`

# Notes
- Task `task_068_orchestrate_conditional_reset_columns_in_cdx_status` was finished via `logics-manager flow finish task` on 2026-08-13.
