## task_085_orchestrate_review_hardening_across_persistence_stats_and_handoff - Orchestrate review hardening across persistence, stats and handoff
> From version: 0.20.14
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: High
> Theme: Review hardening
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-10-04 17:41:50
> Owner: Codex

# AI Context
- Summary: Execute nine correction slices in five delivery waves, prioritizing data integrity and recording regressions for every review finding before closeout.
- Keywords: orchestrate, review, hardening, across, persistence, stats, handoff
- Use when: Starting the consolidated correction chain or checking cross-slice dependencies and final evidence.
- Skip when: Merely reviewing the reports or implementing deferred multi-worktree features.

# Context
- Implement the linked slices against the reviewed baseline, retain the three audit reports as evidence, and settle the linked product brief only when the corrections are verified.

# Plan
- [x] 1. Wave 0: read the three review evidence docs and this chain; reproduce each relevant defect with synthetic temporary data. Map every request AC and secondary observation to a slice. Do not label baseline passing tests as delivery proof.
- [x] 2. Wave 1 (High): preserve force-import recovery boundaries, then serialize memory writes across processes. Validate focused failure-injection and real-process regressions before proceeding.
- [x] 3. Wave 2 (Medium): define and implement failover attempt accounting, then interactive start/end measurement including the history-window gap. Keep registry logical-run identity distinct from history attempts and explicit uncertainty.
- [x] 4. Wave 3 (Medium, after accounting): validate price overrides and undefined relative weights, capture observed headless models per attempt, then consolidate stats finalization and align text/JSON/documentation contracts.
- [x] 5. Wave 4 (Medium): make transcript discovery literal-path-safe, then bind exact native handoff selection and duplicate-ID diagnostics. Preserve preparation boundaries and no-launch failure behavior.
- [x] 6. Wave 5: run npm run lint, npm run test:coverage and cargo test --manifest-path tray/Cargo.toml; run npm pack --dry-run for CLI packaging checks. Use supported-platform CI or targeted equivalent evidence for cross-process locking and path portability. Report unavailable platform proof honestly.
- [x] 7. At each wave update indicators/progress through Logics CLI and record exact test commands/results and request-to-backlog-to-test traceability. Keep execution and regression fixtures free of real credentials, private transcripts and live provider calls.
- [x] 8. Closeout: verify AC1-AC12 and the seven findings plus secondary observations are covered. Run flow validate-closeout, required lint/audit and closeout; settle the linked product brief. Follow user authorization for implementation commits; do not push or publish as part of this chain.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_156_preserve_live_profiles_on_early_force_import_credential_failures`
- `item_157_serialize_memory_appends_across_independent_cli_processes`
- `item_158_account_for_every_headless_failover_attempt_under_its_actual_session`
- `item_159_measure_interactive_usage_at_real_launch_boundaries_without_a_history_cap`
- `item_160_validate_custom_token_rates_and_support_undefined_relative_weights`
- `item_161_persist_observed_model_attribution_for_headless_usage_pricing`
- `item_162_clarify_stats_period_and_cost_contracts_and_remove_duplicate_finalization`
- `item_163_bind_handoff_selection_to_one_exact_native_source_file`
- `item_164_treat_profile_paths_literally_in_native_and_terminal_transcript_discovery`

# Definition of Done (DoD)
- [x] All nine implementation slices and request AC1-AC12 have concrete regression evidence; no finding is closed solely by documentation existing.
- [x] The review coverage map accounts for every primary and secondary observation, including preserved limitations.
- [x] Focused and full Python tests, Rust tests, repository lint, packaging dry-run and required workflow validation pass; platform evidence and any limits are recorded.
- [x] Meaningful waves followed ADR 009: affected docs updated and locally committed as the operator requested.

# AC Traceability
- request-AC1 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC11 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC12 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC2 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC11 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC12 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC3 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC11 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC12 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC4 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC11 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC12 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC5 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC11 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC12 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC6 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC3 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC11 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC12 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC7 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC11 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC12 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC8 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC10 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC11 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC12 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC9 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC10 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC11 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`
- request-AC12 -> This task. Proof: Implemented in 947fafe, 0b34fb3, 7581e17, and 9bfd7cc; 1076 Python tests, 104 Rust tests, project lint and npm pack dry-run passed on macOS. Slice-specific synthetic regressions and coverage map are recorded in item_156 through item_164 and task_085. Source: `9bfd7cc`

# Validation
- Wave 1: `node bin/python-runner.js -m pytest -q test/test_context_store_py.py test/test_commands_context_memory_py.py test/test_run_registry_py.py test/test_profile_data_safety_py.py test/test_commands_backup_py.py` — 68 passed; targeted Ruff checks passed. Native Windows validation is pending.
- Waves 2 and 3: `node bin/python-runner.js -m pytest -q test/test_commands_runs_py.py test/test_run_failover_py.py test/test_usage_delta_py.py test/test_interactive_usage_py.py test/test_commands_launch_py.py test/test_usage_backfill_py.py test/test_usage_weighting_py.py test/test_commands_status_py.py test/test_unvouched_usage_py.py test/test_provider_background_py.py` — 270 passed; targeted Ruff checks passed.
- Wave 4: `node bin/python-runner.js -m pytest -q test/test_handoff_transcript_py.py test/test_commands_launch_py.py test/test_cli_contract_py.py test/test_provider_runtime_helpers_py.py` — 126 passed; targeted Ruff checks passed.
- Final full gates after the last code change: `rtk npm run lint` passed; `rtk npm run test:coverage` passed (1076 Python tests, 83% coverage); `rtk cargo test --manifest-path tray/Cargo.toml` passed (104 Rust tests); `rtk npm pack --dry-run` passed. `logics-manager lint --require-status`, `logics-manager audit --group-by-doc`, and `logics-manager flow validate req_080_harden_reviewed_data_integrity_stats_accounting_and_handoff_recovery task_085_orchestrate_review_hardening_across_persistence_stats_and_handoff` passed. Native Windows and Linux execution was unavailable; lock and path behavior has targeted simulated-platform and macOS process/path coverage.
- rtk npm run lint: passed
- rtk cargo test --manifest-path tray/Cargo.toml: 104 passed
- rtk npm pack --dry-run: passed
- command: `rtk npm run test:coverage` | result: passed | date: 2026-10-04 | note: 1076 Python tests passed at 83% coverage on macOS. Native Windows/Linux runs unavailable; simulated lock paths and literal path regressions passed.
- Finish workflow executed on 2026-10-04.
- Linked backlog/request close verification passed.

# Report
- Implemented all nine slices in local commits `947fafe`, `0b34fb3`, `7581e17`, and `9bfd7cc`. The original review reports remain as evidence; the request coverage map and each backlog's Implementation evidence section name the corresponding regression.
- One run registry record is retained across headless failover while each attempt owns one history record. Interactive usage is measured from a launch-time snapshot when identity is known and left absent when overlap or ownership is uncertain. Custom prices are validated; observed serving models and partial estimate coverage are explicit. Native handoff selection is path-bound and literal profile paths work in discovery.
- No live provider calls, real credentials, native Windows/Linux runs, push, or publication were part of this validation. The recovered transcript remains a live dependency and the receiving agent's understanding cannot be proven by preparation tests.
- Finished on 2026-10-04.
- Linked backlog item(s): `item_156_preserve_live_profiles_on_early_force_import_credential_failures`, `item_157_serialize_memory_appends_across_independent_cli_processes`, `item_158_account_for_every_headless_failover_attempt_under_its_actual_session`, `item_159_measure_interactive_usage_at_real_launch_boundaries_without_a_history_cap`, `item_160_validate_custom_token_rates_and_support_undefined_relative_weights`, `item_161_persist_observed_model_attribution_for_headless_usage_pricing`, `item_162_clarify_stats_period_and_cost_contracts_and_remove_duplicate_finalization`, `item_163_bind_handoff_selection_to_one_exact_native_source_file`, `item_164_treat_profile_paths_literally_in_native_and_terminal_transcript_discovery`
- Related request(s): `req_080_harden_reviewed_data_integrity_stats_accounting_and_handoff_recovery`

# Links
- Request: `req_080_harden_reviewed_data_integrity_stats_accounting_and_handoff_recovery`
- Product brief(s): `prod_056_trustworthy_local_recovery_and_usage_attribution`
- Architecture decision(s): (none yet)

# Execution guidance
- Initial reproduction locations and focused commands live in each backlog slice. First work item: item_156; then item_157. Both are High priority.
- Medium sequence: item_158 -> item_159 -> item_160 -> item_161 -> item_162, followed by item_164 -> item_163. Adjacent steps may share the same module; preserve completed regressions as later steps land.
- Price validation changes need explicit text/JSON compatibility checks for unknown weights; do not silently reinterpret existing numeric fields.
- Handoff exact-native selection is distinct from degraded terminal selection; update parser, help, schema and tests together.
- Before changing user-facing copy, inspect `logics-manager i18n status` and follow the existing project contract. No localization framework is added by this scope.
- Implementation was authorized after corpus preparation; mark complete only after evidence-backed closeout.
