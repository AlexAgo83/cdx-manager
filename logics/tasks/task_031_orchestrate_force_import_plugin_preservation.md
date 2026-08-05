## task_031_orchestrate_force_import_plugin_preservation - Orchestrate force import plugin preservation
> From version: 0.12.3
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Reproduce the issue #7 flow with the smallest fixture: create an existing session profile containing a local plugin marker and import an auth-bearing bundle for that same session with `force=True`; confirm the marker is currently lost.
- [ ] 2. Inspect real Codex plugin installation layout in a controlled temp profile if needed, then preserve only the path(s) required for installed plugins to survive.
- [ ] 3. Patch `import_bundle()` at the force import root cause: record preservable local plugin-state paths before renaming `session_root`, restore them from `backup_root` after bundle file writes and before backup deletion, and route failures through `_restore_import_backup()`.
- [ ] 4. Keep `item_022` behavior intact by leaving the authless `include_auth` guard before filesystem mutation and by preserving the existing pre-validation and per-session rollback tests.
- [ ] 5. Add focused tests in `test/test_session_service_py.py` for plugin preservation, restoration failure rollback, selected-session isolation, and authless guard non-regression; add a small CLI/help or README assertion only where the repo already tests import help/docs.
- [ ] 6. Run focused import tests first, then the relevant CLI/session-service test files, then `logics-manager lint --require-status` and `logics-manager audit` before closeout.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_040_preserve_local_plugin_state_during_force_import`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1, request-AC2, request-AC3, request-AC4, request-AC5, request-AC6 -> `item_040_preserve_local_plugin_state_during_force_import`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# AI Context
- Summary: Orchestrate force import plugin preservation
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_020_prevent_cdx_import_force_from_silently_discarding_local_plugins`
- Product brief(s): `prod_010_force_import_preservation_for_local_plugin_state`
- Architecture decision(s): (none yet)
