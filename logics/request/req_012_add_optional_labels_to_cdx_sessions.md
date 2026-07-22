## req_012_add_optional_labels_to_cdx_sessions - Add optional labels to cdx sessions
> From version: 0.11.0
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Low
> Theme: Operator workflow
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# Needs
- Users can already name sessions, but names often encode stable launch identity while users still need a lightweight way to group or annotate sessions by account purpose, workspace, client placeholder, or operational role.
- The label must stay optional and quiet: existing users with no labels should see the same compact list and status tables they see today.
- The feature should fit the existing session metadata model and table conventions instead of adding a new tagging system or changing launch behavior.

# Context
- Session records are persisted as versioned JSON in `sessions.json`; `create_session` builds the root session metadata in `src/session_service.py`, and `format_list_rows` / `_status_row_from_session` flatten records for display and JSON output.
- The default `cdx` list already uses conditional columns: provider appears only when useful, launch appears only when at least one row has launch settings, and `_pad_table` handles alignment.
- `cdx status` builds rows from service-provided status data and already has compact and full variants; the label should not bloat `--small` unless the implementation deliberately keeps it concise.
- `cdx set` / `cdx unset` are launch-setting commands. A session label is identification metadata, so it should not live under `launch` and should not affect provider command arguments, auth checks, priority selection, or launch history semantics.
- Export/import and copy/rename paths should preserve labels because they preserve session identity metadata.

# Acceptance criteria
- AC1: A user can set one optional label on a session with a clear CLI command, and the value is persisted on the session record outside the `launch` dictionary.
- AC2: A user can clear a session label; clearing removes or nulls the stored label so unlabeled sessions remain indistinguishable from legacy records.
- AC3: Label input is normalized and validated: trim surrounding whitespace, reject empty values for set operations, reject control characters, and enforce a bounded length.
- AC4: `cdx` list output adds a `LABEL` column only when at least one listed session has a label; unlabeled rows render as `-`, and output without labels remains unchanged.
- AC5: `cdx status` full output adds a `LABEL` column only when at least one status row has a label; `cdx status --small` stays compact unless the implementation proves the column remains readable.
- AC6: `cdx --json`, `cdx status --json`, and the label command JSON response expose the label consistently for automation consumers.
- AC7: Session copy, rename, export, and import preserve labels; launch, auth, runtime, ready/next/select, and history behavior are otherwise unchanged.
- AC8: Help and README command documentation describe the label command and the conditional label column behavior.
- AC9: Focused tests cover set, clear, validation failures, conditional list/status columns, JSON payloads, and preservation through copy/export/import.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_005_session_labeling_for_cdx`
- Architecture decision(s): (none yet)

# References
- src/session_service.py
- src/cli_render.py
- src/status_view.py
- src/cli_args.py
- src/cli_commands.py
- src/cli.py
- README.md
- test/test_session_service_py.py
- test/test_cli_py.py

# AI Context
- Summary: Add optional labels to cdx sessions
- Keywords: request-chain-scaffold, add optional labels to cdx sessions, development-ready
- Use when: You need to implement or review the scaffolded workflow for Add optional labels to cdx sessions.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_032_optional_session_labels_in_cli_list_and_status_surfaces`
