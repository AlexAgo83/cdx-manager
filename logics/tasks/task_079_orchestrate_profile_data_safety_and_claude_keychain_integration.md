## task_079_orchestrate_profile_data_safety_and_claude_keychain_integration - Orchestrate profile data safety and Claude keychain integration
> From version: 0.20.8
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 95%
> Progress: 100%
> Complexity: High
> Theme: Profile data safety and authentication
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-09-06 11:55:44
> Owner: Codex

# AI Context
- Summary: Implement the five bounded slices, with data preservation first and shared credential resolution before dependent lifecycle operations.
- Keywords: merge, rollback, keychain, copy, quota, export, rename
- Use when: Delivering this request end to end.
- Skip when: Only reviewing or proposing unrelated credential features.

# Context
- This is the executable orchestration task for the five linked backlog items; it owns implementation and final validation, not merely creation of more tasks.
- The review reproduced destructive merge rollback, keychain-directory copying, absent quota probes and incomplete export collection. Rename identity loss was established by code inspection and still requires a synthetic keychain regression.
- Keep the source credential backend and namespace aligned with the installed provider. Do not hard-code an unverified service-name algorithm.
- The copy slice has two steps: High-priority non-traversal protection, then credential-copy completion after the quota slice supplies the resolver.
- Export chooses the explicit-unsupported option already allowed by the request. Full keychain portability is outside this delivery.
- No additional approval is needed for scoped implementation with fake fixtures; actual operator credential mutation is not required by the automated plan.

# Plan
- [x] 1. Trace merge rollback and credential consumers; confirm the local provider's keychain namespace, credential shape and precedence without inspecting operator secrets. Record version and synthetic evidence.
- [x] 2. Wave 1 (High): implement merge rollback preservation and the non-traversal portion of profile copy. Add failure-injection checks before recording the wave outcome.
- [x] 3. Wave 2 (enabling Medium work): implement profile-scoped credential resolution and quota refresh; finish isolated credential copy and destination rollback using the verified resolver.
- [x] 4. Wave 3 (Medium): implement explicit unsupported-auth-export refusal, text/JSON error contracts and README guidance; verify an existing --force destination survives preflight failure.
- [x] 5. Wave 4 (Medium): migrate renamed profile credentials with collision handling and staged commit/rollback; verify file-backed behavior and record cross-slice AC6 evidence.
- [x] 6. Run scoped tests as each slice lands, then run final project lint, Python tests, Rust tests and npm packaging dry-run once. Record actual commands and outcomes, including unavailable platform checks.
- [x] 7. Apply ADR 009 at each meaningful wave: update affected Logics docs and progress using the CLI, leave the repository commit-ready, and record implementation evidence against all six request ACs before closeout.

# Backlog
- `item_140_preserve_existing_profiles_on_merge_import_failure`
- `item_141_copy_claude_profiles_without_traversing_the_system_keychain`
- `item_142_read_profile_scoped_claude_keychain_credentials_for_quota_refresh`
- `item_143_report_unsupported_keychain_credential_exports_explicitly`
- `item_144_preserve_claude_keychain_authentication_across_session_rename`

# Definition of Done (DoD)
- [x] All five slices satisfy their acceptance criteria, including their error paths.
- [x] Every request AC has concrete implementation and test evidence; no scaffold text is presented as proof of delivery.
- [x] No external keychain directory is copied and no unrelated profile/default credential is overwritten.
- [x] Export text/JSON behavior and operator documentation reflect the unsupported keychain portability decision.
- [x] Project lint, Python tests, Rust tests and packaging dry-run pass; platform limitations are recorded explicitly.
- [x] Linked backlog/request/product status is settled through CLI closeout only after the implementation is delivered.
- [x] Meaningful waves followed ADR 009 and left commit decisions to the operator.

# AC Traceability
- request-AC1 -> This task. Proof: `src/session_backup.py` `import_bundle` snapshots the existing profile (symlinks preserved) plus record and state into a recovery directory before merge, and restores them on failure; a failed recovery raises with the retained recovery path. Tests: `test_merge_failure_preserves_original_files_record_and_state`, `test_merge_state_failure_restores_state_and_failed_recovery_keeps_snapshot`.
- request-AC2 -> This task. Proof: `src/session_service.py` `copy_session` excludes `claude-home/Library/Keychains` from the profile copy, relinks the macOS keychain, and copies only the source profile's keychain entry through `copy_keychain_credentials` (`src/claude_credentials.py`), restoring the destination entry and profile on failure. Tests: `test_copy_never_reads_external_keychain_and_copies_only_profile_entry`, `test_copy_failure_restores_existing_destination_credential_and_profile`.
- request-AC3 -> This task. Proof: `src/claude_usage.py` `_read_claude_credentials` reads the profile-scoped keychain entry before legacy credential files, and `src/provider_runtime.py` `_read_claude_launch_oauth_token` stops injecting a launch token when the keychain owns the credential. Keychain errors surface as errors, not as "missing", and never echo tokens. Tests: `test_keychain_quota_precedence_and_launch_token_isolation`, `test_keychain_errors_are_not_missing_and_never_leak_tokens`.
- request-AC4 -> This task. Proof: `src/session_backup.py` `export_bundle` refuses `--include-auth` before writing anything when any selected Claude profile is keychain-backed, naming the profiles in both text and JSON; an inaccessible keychain is an explicit error. README documents the limitation and the workaround. Tests: `test_export_refusal_preserves_force_destination_for_mixed_profiles`, `test_export_refusal_has_nonzero_text_and_json_cli_outcomes`, `test_export_denied_keychain_never_replaces_output`.
- request-AC5 -> This task. Proof: `src/session_service.py` `rename_session` stages the destination keychain entry through `copy_keychain_credentials` (refusing an existing destination entry), commits only after the profile move and store rename succeed, deletes the old entry afterwards, and rolls the profile and entry back on any failure. Tests: `test_rename_moves_only_profile_authentication`, `test_rename_store_failure_and_collision_preserve_original`, `test_rename_cleanup_failure_keeps_working_destination`, `test_rename_write_verification_and_directory_failures_preserve_source`.
- request-AC6 -> This task. Proof: `src/claude_credentials.py` bounds the `security` runner, suppresses provider output, normalizes the namespace, keeps credentials out of process arguments with read-back verification, and is inert off macOS. Tests: `test_native_runner_bounds_time_and_suppresses_provider_output`, `test_namespace_normalizes_unicode_and_rejects_hash_collisions`, `test_writes_keep_credentials_out_of_process_arguments_and_verify_readback`, `test_other_platforms_do_not_call_security`. Project validation: 1006 Python tests, 96 Rust tests, lint and packaging dry-run all passed on 2026-09-06.

# Validation
- `node bin/python-runner.js -m pytest test/test_profile_data_safety_py.py -q` -> 17 passed (slice-scoped fixtures with injected failures).
- `npm run lint` -> All checks passed.
- `npm test` -> 1006 passed in 12.40s.
- `cargo test --manifest-path tray/Cargo.toml` -> 96 passed; 0 failed.
- `npm pack --dry-run` -> cdx-manager-0.20.8.tgz, 165 files.
- Platform limitation: keychain behavior is exercised through a faked `security` runner; no operator credential was read or mutated. The non-macOS path is covered by `test_other_platforms_do_not_call_security`.
- Prior review baseline was 989 Python and 96 Rust tests; the suite now stands at 1006 Python tests.
- lint OK; 1006 Python tests; 96 Rust tests; npm pack --dry-run OK
- Finish workflow executed on 2026-09-06.
- Linked backlog/request close verification passed.

# Report
- Delivered. All five slices are implemented across `src/claude_credentials.py` (new), `src/session_backup.py`, `src/session_service.py`, `src/claude_usage.py`, `src/provider_runtime.py`, with operator guidance in README. Keychain portability stays explicitly unsupported on export, as the request allows. Full project validation passed. Delivered as four wave commits on `main`: keychain credential resolution, merge-import preservation, cp/ren credential isolation, export refusal.
- Finished on 2026-09-06.
- Linked backlog item(s): `item_140_preserve_existing_profiles_on_merge_import_failure`, `item_141_copy_claude_profiles_without_traversing_the_system_keychain`, `item_142_read_profile_scoped_claude_keychain_credentials_for_quota_refresh`, `item_143_report_unsupported_keychain_credential_exports_explicitly`, `item_144_preserve_claude_keychain_authentication_across_session_rename`
- Related request(s): `req_070_review_findings_profile_data_safety_and_keychain_integration`

# Links
- Request: `req_070_review_findings_profile_data_safety_and_keychain_integration`
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
