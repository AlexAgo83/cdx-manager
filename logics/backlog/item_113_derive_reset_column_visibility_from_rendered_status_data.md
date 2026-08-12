## item_113_derive_reset_column_visibility_from_rendered_status_data - Derive reset-column visibility from rendered status data
> From version: 0.18.6
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Low
> Theme: Status presentation
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: derive, reset, column, visibility, rendered, status, data
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- The fixed status headers reserve three reset columns even when every cell is empty, reducing readability for common weekly-only or no-reset account shapes.
- The six fixed usage values couple column construction to headers, so an ad-hoc string replacement could misalign disabled and small rows.

# Scope
- In:
  - Compute independent visibility flags once from the rendered rows before building normal or small headers.
  - Include only the corresponding bonus-reset count and reset-time values in each row while preserving alignment and existing formatting.
  - Treat only a positive numeric reset_credits_available value as a visible bonus-reset signal.
- Out:
  - Changing reset values, hiding five-hour or weekly quota percentage columns, or adding presentation preferences.

# Acceptance criteria
- AC1: Empty bonus, five-hour, and weekly reset columns disappear independently.
- AC2: A single row with a value restores only its matching header and cells.
- AC3: Normal and small tables remain aligned for disabled and mixed-provider rows.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Empty bonus, five-hour, and weekly reset columns disappear independently.
- request-AC2 -> This backlog slice. Proof: AC2: A single row with a value restores only its matching header and cells.
- request-AC3 -> This backlog slice. Proof: AC3: Normal and small tables remain aligned for disabled and mixed-provider rows.
- request-AC5 -> This backlog slice. Proof: AC3: Normal and small tables remain aligned for disabled and mixed-provider rows.

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
