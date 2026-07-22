## item_032_optional_session_labels_in_cli_list_and_status_surfaces - Optional session labels in CLI list and status surfaces
> From version: 0.11.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Low
> Theme: Operator workflow
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- Session names are stable launch identifiers, so users avoid renaming them just to express a temporary or human grouping such as a workspace, account role, or client placeholder.
- Adding label visibility unconditionally would make the already dense status table worse for users who do not use labels.
- Putting labels under `launch` would mix display metadata with provider behavior and make existing launch-setting commands carry unrelated responsibility.

# Scope
- In:
  - Add a root-level optional `label` field to session records, with a small service API such as `set_session_label(name, label)` and `clear_session_label(name)` or one combined updater.
  - Add a dedicated CLI surface, recommended as `cdx label <name> <label> [--json]` and `cdx label <name> --clear [--json]`, rather than extending launch-setting `set` / `unset`.
  - Validate labels with the same defensive style as session names: strip surrounding whitespace, reject empty set values, reject ASCII control characters, and enforce a bounded maximum length such as 64 characters.
  - Include `label` in `format_list_rows()` and `_status_row_from_session()` so text and JSON outputs use the same source.
  - Add a conditional `LABEL` column to `_format_sessions()` and full `_format_status_rows()` only when any row has a non-empty label; render unlabeled rows as `-`; keep `--small` compact.
  - Preserve labels through `copy_session`, `rename_session`, `_build_export_session_record`, and import replacement records.
  - Update help text, README command table, and JSON-output documentation for the new command and optional column.
  - Add focused unit tests in `test/test_session_service_py.py` and `test/test_cli_py.py` for persistence, validation, text output, JSON payloads, and copy/export/import preservation.
- Out:
  - Multiple labels per session.
  - Filtering commands such as `cdx --label X`, `cdx status --label X`, or label-aware `cdx select`.
  - Label color, formatting themes, or terminal badge rendering.
  - Automatic labels inferred from provider account email, workspace path, or auth state.
  - Database or store schema migration beyond tolerating legacy sessions without a label key.

# Acceptance criteria
- `cdx label main work` persists `label: "work"` on the `main` session record outside `launch` and updates `updatedAt`.
- `cdx label main --clear` removes or clears the label and updates `updatedAt`; a following `cdx` list has no `LABEL` column if no other labels exist.
- Labels with only whitespace, control characters, or more than the allowed maximum fail with a short `CdxError` message and do not mutate the session.
- The default `cdx` table is byte-for-byte unchanged when no sessions have labels, aside from existing timestamp variability; when one label exists, the table includes `LABEL` and unlabeled rows show `-`.
- The full `cdx status` table includes `LABEL` only when any status row has a label; `cdx status --small` remains unchanged.
- `cdx --json` and `cdx status --json` include `label` for labeled sessions and omit or null it consistently for unlabeled sessions.
- Copy, rename, export, and import preserve the label while keeping auth homes, launch settings, and status data behavior unchanged.
- Tests cover the service API, CLI command, validation errors, conditional columns, JSON output, and preservation paths.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: `cdx label main work` persists `label: "work"` on the `main` session record outside `launch` and updates `updatedAt`.
- request-AC2 -> This backlog slice. Proof: `cdx label main --clear` removes or clears the label and updates `updatedAt`; a following `cdx` list has no `LABEL` column if no other labels exist.
- request-AC3 -> This backlog slice. Proof: Labels with only whitespace, control characters, or more than the allowed maximum fail with a short `CdxError` message and do not mutate the session.
- request-AC4 -> This backlog slice. Proof: The default `cdx` table is byte-for-byte unchanged when no sessions have labels, aside from existing timestamp variability; when one label exists, the table includes `LABEL` and unlabeled rows show `-`.
- request-AC5 -> This backlog slice. Proof: The full `cdx status` table includes `LABEL` only when any status row has a label; `cdx status --small` remains unchanged.
- request-AC6 -> This backlog slice. Proof: `cdx --json` and `cdx status --json` include `label` for labeled sessions and omit or null it consistently for unlabeled sessions.
- request-AC7 -> This backlog slice. Proof: Copy, rename, export, and import preserve the label while keeping auth homes, launch settings, and status data behavior unchanged.
- request-AC8 -> This backlog slice. Proof: Tests cover the service API, CLI command, validation errors, conditional columns, JSON output, and preservation paths.
- request-AC9 -> This backlog slice. Proof: Tests cover the service API, CLI command, validation errors, conditional columns, JSON output, and preservation paths.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_005_session_labeling_for_cdx`
- Architecture decision(s): (none yet)
- Request: `req_012_add_optional_labels_to_cdx_sessions`
- Primary task(s): `task_023_orchestrate_optional_session_labels`

# AI Context
- Summary: Optional session labels in CLI list and status surfaces
- Keywords: scaffolded-backlog, optional session labels in cli list and status surfaces, implementation-ready
- Use when: Implementing the scaffolded slice for Optional session labels in CLI list and status surfaces.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.

# Tasks
- `task_023_orchestrate_optional_session_labels`

# Notes
- Task `task_023_orchestrate_optional_session_labels` was finished via `logics-manager flow finish task` on 2026-07-23.
