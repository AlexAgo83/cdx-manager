## task_023_orchestrate_optional_session_labels - Orchestrate optional session labels
> From version: 0.11.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Start with the session-service data model: add label validation, root-level persistence, and service methods for set and clear.
- [x] 2. Propagate label into list and status row builders without changing sort order, priority selection, auth checks, launch settings, or runtime state.
- [x] 3. Add the dedicated `cdx label` parser and handler, wire it into the command registry, and return concise text and JSON responses.
- [x] 4. Add conditional `LABEL` columns to the default list and full status formatters, leaving no-label and small-status output compact.
- [x] 5. Preserve labels in copy, rename, export, and import paths.
- [x] 6. Update help and README documentation.
- [x] 7. Run focused CLI and service tests, then the relevant unittest files.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_032_optional_session_labels_in_cli_list_and_status_surfaces`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: `cdx label <name> <label>` is implemented via `handle_label`, `set_session_label`, and root-level `label` persistence outside `launch`; covered by `test_label_command_updates_json_and_conditional_list_column`.
- request-AC2 -> This task. Proof: `cdx label <name> --clear` calls `clear_session_label`, removes the `label` key, and drops the conditional `LABEL` column when no labels remain; covered by `test_label_command_updates_json_and_conditional_list_column`.
- request-AC3 -> This task. Proof: `_normalize_session_label` trims labels, rejects empty/control-character/overlength labels, and leaves the previous label intact on failure; covered by `test_session_label_set_clear_and_validation` and `test_label_command_rejects_invalid_input_without_mutating`.
- request-AC4 -> This task. Proof: `_format_sessions` adds `LABEL` only when any list row has a label and renders unlabeled rows as `-`; covered by `test_label_command_updates_json_and_conditional_list_column`.
- request-AC5 -> This task. Proof: `_format_status_rows` adds `LABEL` only in full status output when any row has a label and keeps `--small` compact; covered by `test_status_full_shows_label_column_only_when_present` and `test_status_small_hides_metadata_columns`.
- request-AC6 -> This task. Proof: `format_list_rows`, `_status_row_from_session`, and the label command JSON response expose label values; covered by `test_label_command_updates_json_and_conditional_list_column` and `test_status_json_global_and_detail_contract`.
- request-AC7 -> This task. Proof: `copy_session`, `rename_session`, `_build_export_session_record`, and import replacement records preserve root-level labels without touching launch/auth/runtime behavior; covered by `test_session_label_is_preserved_by_copy_and_rename` and `test_export_import_round_trip_without_auth`.
- request-AC8 -> This task. Proof: `cdx --help` and README command documentation now describe `cdx label <name> <label>` and `cdx label <name> --clear`, including conditional `LABEL` columns.
- request-AC9 -> This task. Proof: `python3 -m unittest discover -s test` passed with 479 tests, including focused service and CLI coverage for set, clear, validation failures, conditional columns, JSON payloads, and preservation paths.

# Validation
- Run `python3 -m logics_manager lint --require-status`.
- Run scaffold command tests.
- python3 -m unittest discover -s test passed: 479 tests OK. Focused suites also passed: test_session_service_py.py 88 tests OK and test_cli_py.py 198 tests OK.
- Finish workflow executed on 2026-07-23.
- Linked backlog/request close verification passed.

# Report
- Implementation complete.
- Finished on 2026-07-23.
- Linked backlog item(s): `item_032_optional_session_labels_in_cli_list_and_status_surfaces`
- Related request(s): `req_012_add_optional_labels_to_cdx_sessions`

# AI Context
- Summary: Orchestrate optional session labels
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_012_add_optional_labels_to_cdx_sessions`
- Product brief(s): `prod_005_session_labeling_for_cdx`
- Architecture decision(s): (none yet)
