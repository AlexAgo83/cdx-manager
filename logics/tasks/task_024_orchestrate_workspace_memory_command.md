## task_024_orchestrate_workspace_memory_command - Orchestrate workspace memory command
> From version: 0.11.2
> Schema version: 1.0
> Status: Ready
> Understanding: 95
> Confidence: 90
> Progress: 0
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- Recent Codex and Claude Code releases make memory more visible, but this task should still ship the smallest useful `cdx` surface: scoped Markdown memory plus append.
- Provider-native memory and diagnostics are useful follow-ups. Do not write Codex SQLite memory, Claude Code auto memory, `CLAUDE.md`, plugin files, or model settings in this implementation.

# Plan
- [ ] 1. Confirm the current `cdx context` and `cdx handoff` flow so the implementation reuses existing storage instead of adding a second memory system.
- [ ] 2. Add the smallest context-store append helper with trimming, empty-input rejection, clean newline handling, and atomic write.
- [ ] 3. Add minimal scope resolution for current workspace, global memory, and `--project <name-or-path>`.
- [ ] 4. Refactor only enough CLI context handling to share behavior between `cdx context` and `cdx memory`.
- [ ] 5. Wire `memory` into command dispatch and help text, with `cdx memory` defaulting to current-workspace view/show.
- [ ] 6. Update README documentation for the memory command, scope flags, and supported storage boundary.
- [ ] 7. Add focused tests for append, current/global/project scopes, JSON output, and backward compatibility.
- [ ] 8. Capture follow-up notes for provider-native sync/export and version/diagnostic doctor checks without implementing them in this slice.
- [ ] 9. Run focused tests first, then the standard lint/test checks required by the workflow.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_033_scoped_memory_alias_and_append_command`

# Definition of Done (DoD)
- [ ] The scoped `cdx memory` command is implemented against the existing context store.
- [ ] Current-workspace, global, and explicit project memory scopes are covered by focused tests.
- [ ] `append` behavior is covered for missing files, existing files, newline boundaries, and empty input rejection.
- [ ] `cdx context` and `cdx handoff` backward compatibility is verified.
- [ ] README/help documentation describes the supported memory storage boundary.
- [ ] Provider-native memory sync/export and provider version diagnostics are explicitly left as follow-ups, not half-implemented.
- [ ] Logics lint, audit, and request validation pass.

# AC Traceability
- request-AC1 -> Task plan steps 1, 4, and 5. Proof deferred until implementation verifies `cdx memory` and `cdx memory view`.
- request-AC2 -> Task plan steps 3, 4, and 7. Proof deferred until implementation verifies `--global`.
- request-AC3 -> Task plan steps 3, 4, and 7. Proof deferred until implementation verifies `--project <name-or-path>`.
- request-AC4 -> Task plan steps 3 and 7. Proof deferred until implementation verifies mutual exclusion and default scope.
- request-AC5 -> Task plan steps 4, 5, and 7. Proof deferred until implementation verifies selected-scope command parity.
- request-AC6 -> Task plan steps 2, 3, 4, and 7. Proof deferred until implementation verifies append across scopes.
- request-AC7 -> Task plan steps 2 and 7. Proof deferred until implementation verifies append file creation and newline behavior.
- request-AC8 -> Task plan steps 4 and 7. Proof deferred until implementation verifies JSON scope metadata.
- request-AC9 -> Task plan steps 1, 4, and 7. Proof deferred until compatibility tests pass.
- request-AC10 -> Task plan steps 5 and 6. Proof deferred until help and README are updated.
- request-AC11 -> Task plan steps 7 and 9. Proof deferred until focused tests and workflow validation pass.

# Validation
- Run `python3 -m logics_manager lint --require-status`.
- Run scaffold command tests.

# Report
- Not started. Ready for an implementation agent.

# AI Context
- Summary: Orchestrate workspace memory command
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_013_add_a_small_workspace_memory_command_to_cdx`
- Product brief(s): `prod_006_workspace_memory_command_for_cdx`
- Architecture decision(s): (none yet)
