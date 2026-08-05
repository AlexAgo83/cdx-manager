## task_031_orchestrate_force_import_plugin_preservation - Orchestrate force import plugin preservation
> From version: 0.12.3
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 90%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: cdx

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Reproduce the issue #7 flow with the smallest fixture: create an existing session profile containing a local plugin marker and import an auth-bearing bundle for that same session with `force=True`; confirm the marker is currently lost.
- [x] 2. Inspect real Codex plugin installation layout in a controlled temp profile if needed, then preserve only the path(s) required for installed plugins to survive.
- [x] 3. Patch `import_bundle()` at the force import root cause: record preservable local plugin-state paths before renaming `session_root`, restore them from `backup_root` after bundle file writes and before backup deletion, and route failures through `_restore_import_backup()`.
- [x] 4. Keep `item_022` behavior intact by leaving the authless `include_auth` guard before filesystem mutation and by preserving the existing pre-validation and per-session rollback tests.
- [x] 5. Add focused tests in `test/test_session_service_py.py` for plugin preservation, restoration failure rollback, selected-session isolation, and authless guard non-regression; add a small CLI/help or README assertion only where the repo already tests import help/docs.
- [x] 6. Run focused import tests first, then the relevant CLI/session-service test files, then `logics-manager lint --require-status` and `logics-manager audit` before closeout.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_040_preserve_local_plugin_state_during_force_import`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1, request-AC2, request-AC3, request-AC4, request-AC5, request-AC6 -> `item_040_preserve_local_plugin_state_during_force_import`. Proof deferred to slice closeout.
- request-AC1 -> This task. Proof: `import_bundle()` records existing `plugins/` before the force rename and restores it from backup after bundle writes; covered by `test_force_import_with_auth_preserves_local_plugins`.
- request-AC2 -> This task. Proof: plugin restore copy failures raise `CdxError` and flow through `_restore_import_backup()`; covered by `test_force_import_plugin_restore_failure_rolls_back`.
- request-AC3 -> This task. Proof: the authless force guard remains before filesystem mutation; covered by `test_force_import_without_auth_refuses_to_overwrite_existing_credentials` plus existing corrupt profile prevalidation tests.
- request-AC4 -> This task. Proof: merge mode code path is unchanged and existing merge tests still pass in `test/test_session_service_py.py`.
- request-AC5 -> This task. Proof: `src/cli.py`, `README.md`, and `changelogs/CHANGELOGS_0_12_3.md` document auth payload scope and force-import plugin preservation.
- request-AC6 -> This task. Proof: `test_force_import_with_auth_preserves_local_plugins` and `test_force_import_preserves_plugins_only_for_selected_sessions` cover the issue #7 auth-bearing force import and selected-session isolation.

# Validation
- (no validation recorded yet)
- 2026-08-05: node bin/python-runner.js -m pytest test/test_session_service_py.py test/test_cli_py.py passed: 305 passed
- 2026-08-05: npm test passed: 507 passed
- 2026-08-05: npm run lint passed with .venv first on PATH after uv sync: All checks passed
- 2026-08-05: logics-manager lint --require-status passed: OK
- 2026-08-05: logics-manager audit passed: OK with unrelated companion Mermaid warnings
- Finish workflow executed on 2026-08-05.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-05.
- Linked backlog item(s): `item_040_preserve_local_plugin_state_during_force_import`
- Related request(s): `req_020_prevent_cdx_import_force_from_silently_discarding_local_plugins`

# AI Context
- Summary: Orchestrate force import plugin preservation
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_020_prevent_cdx_import_force_from_silently_discarding_local_plugins`
- Product brief(s): `prod_010_force_import_preservation_for_local_plugin_state`
- Architecture decision(s): (none yet)
