## task_024_orchestrate_workspace_memory_command - Orchestrate workspace memory command
> From version: 0.11.2
> Schema version: 1.0
> Status: Done
> Understanding: 100
> Confidence: 95
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: codex

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- Recent Codex and Claude Code releases make memory more visible, but this task should still ship the smallest useful `cdx` surface: scoped Markdown memory plus append.
- Provider-native memory and diagnostics are useful follow-ups. Do not write Codex SQLite memory, Claude Code auto memory, `CLAUDE.md`, plugin files, or model settings in this implementation.

# Plan
- [ ] 1. Confirm the current `cdx context` and `cdx handoff` flow so the implementation reuses existing storage instead of adding a second memory system.
- [ ] 2. Add the smallest context-store append helper with trimming, empty-input rejection, clean newline handling, and atomic write.
- [ ] 3. Add minimal scope resolution for current workspace, global memory, free-form project names, and existing `--project <path>` values.
- [ ] 4. Refactor only enough CLI context handling to share behavior between `cdx context` and `cdx memory`.
- [ ] 5. Wire `memory` into command dispatch and help text, with `cdx memory` defaulting to current-workspace view/show.
- [ ] 6. Add bounded `cdx memory list` output for global memory, named project memories, and current workspace memory when present.
- [ ] 7. Update README documentation for the memory command, scope flags, `list`, and supported storage boundary.
- [ ] 8. Add focused tests for append, list, current/global/project scopes, JSON output, and backward compatibility.
- [ ] 9. Capture follow-up notes for provider-native sync/export and version/diagnostic doctor checks without implementing them in this slice.
- [ ] 10. Run focused tests first, then the standard lint/test checks required by the workflow.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_033_scoped_memory_alias_and_append_command`

# Definition of Done (DoD)
- [x] The scoped `cdx memory` command is implemented against the existing context store.
- [x] Current-workspace, global, and explicit project memory scopes are covered by focused tests.
- [x] Free-form `--project A` and path-based `--project /path/to/repo` behavior are both covered.
- [x] `cdx memory list` is covered without repository discovery.
- [x] `append` behavior is covered for missing files, existing files, newline boundaries, and empty input rejection.
- [x] `cdx context` and `cdx handoff` backward compatibility is verified.
- [x] README/help documentation describes the supported memory storage boundary.
- [x] Provider-native memory sync/export and provider version diagnostics are explicitly left as follow-ups, not half-implemented.
- [x] Logics lint, audit, and request validation pass.

# AC Traceability
- request-AC1 -> Task AC1. Proof: implemented by `handle_memory` show/view handling in `src/cli_commands.py`; covered by `test_memory_commands_support_current_global_project_and_list`.
- request-AC2 -> Task AC2. Proof: implemented by `--global` memory scope resolution in `src/cli_commands.py`; covered by `test_memory_commands_support_current_global_project_and_list`.
- request-AC3 -> Task AC3. Proof: implemented by name/path project scope resolution in `src/cli_commands.py`; covered by `test_memory_commands_support_current_global_project_and_list`.
- request-AC4 -> Task AC4. Proof: implemented by `_parse_memory_args` mutual-exclusion/default-scope handling; covered by `test_memory_rejects_empty_append_and_conflicting_scope_flags`.
- request-AC5 -> Task AC5. Proof: implemented by `memory path/init/edit/clear/set` branches reusing context-store path helpers in `src/cli_commands.py`; JSON behavior follows `_json_success` payloads.
- request-AC6 -> Task AC6. Proof: implemented by `append_context_path` and `handle_memory append`; covered by current/global/project assertions in `test_memory_commands_support_current_global_project_and_list`.
- request-AC7 -> Task AC7. Proof: implemented by `_list_memory_entries` and `handle_memory list`; covered by `test_memory_commands_support_current_global_project_and_list`.
- request-AC8 -> Task AC8. Proof: implemented by `append_context_path`; covered by `test_append_context_preserves_existing_content_and_rejects_empty`.
- request-AC9 -> Task AC9. Proof: implemented by `_memory_payload` and JSON branches in `handle_memory`; covered by JSON assertions in `test_memory_commands_support_current_global_project_and_list`.
- request-AC10 -> Task AC10. Proof: backward compatibility preserved by keeping `handle_context`; covered by existing context/handoff tests and full `pytest` run.
- request-AC11 -> Task AC11. Proof: documented in `README.md` command table, JSON list, data layout, and provider-private memory boundary.
- request-AC12 -> Task AC12. Proof: covered by focused context/CLI tests plus full validation: `PYTHONPATH=src python3 -m pytest -q` and `python3 -m ruff check src test`.

# Validation
- Run `python3 -m logics_manager lint --require-status`.
- Run scaffold command tests.
- Ran `PYTHONPATH=src python3 -m pytest -q`: 485 passed.
- Ran `python3 -m ruff check src test`: all checks passed.
- Finish workflow executed on 2026-07-28.
- Linked backlog/request close verification passed.

# Report
- Implemented scoped `cdx memory` command with current, global, free-form project, path-project, append, list, path, init, edit, clear, set, and JSON behavior.
- Updated README and Logics context pack.
- Finished on 2026-07-28.
- Linked backlog item(s): `item_033_scoped_memory_alias_and_append_command`
- Related request(s): `req_013_add_a_small_workspace_memory_command_to_cdx`

# AI Context
- Summary: Orchestrate workspace memory command
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_013_add_a_small_workspace_memory_command_to_cdx`
- Product brief(s): `prod_006_workspace_memory_command_for_cdx`
- Architecture decision(s): (none yet)
