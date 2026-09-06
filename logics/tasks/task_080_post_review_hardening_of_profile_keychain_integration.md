## task_080_post_review_hardening_of_profile_keychain_integration - Post-review hardening of profile keychain integration
> From version: 0.20.9
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 95%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-09-06 12:15:21

# AI Context
- Summary: Implement the eight review fixes and their regression tests before 0.20.9 ships.
- Keywords: post, review, hardening, profile, keychain, integration
- Use when: Touching profile removal, copy, rename or Claude credential resolution.
- Skip when: Working on Codex or Antigravity credential handling.

# Definition of Done (DoD)
- [x] The backlog scope is implemented.
- [x] Acceptance criteria are covered.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# Backlog
- `item_145_post_review_hardening_of_profile_keychain_integration`

# Acceptance criteria
- AC1: Removing a session deletes that profile's keychain credential and no other, frees the name for reuse, and reports a deletion failure without pretending the session survived.
- AC2: A keychain that cannot answer falls back to the profile's credential files for quota refresh and launch, and is reported as an error only when no file credential answers either.
- AC3: A custom Claude OAuth endpoint blocks keychain writes but no longer blocks reads, so unrelated flows keep working.
- AC4: The remaining low-severity findings that can fail unsafely are fixed: the copy guard cannot follow a keychain symlink, a retained destination profile is named, a dangling link cannot fail a merge snapshot, and a cross-drive bundle path is refused as a CdxError.
- AC5: Project lint, Python tests and Rust tests pass.

# Plan
- [x] 1. Delete the profile's keychain credential when a session is removed, and when a non-Claude source overwrites a Claude destination.
- [x] 2. Add a tolerant read that returns None when the keychain cannot answer, and use it wherever a credential file can still answer.
- [x] 3. Move the custom-OAuth guard from identity resolution to the two write functions.
- [x] 4. Make the remaining low findings fail safe: name-matched Keychains exclusion with symlinks kept as links, a named retained destination profile, dangling links tolerated in the merge snapshot, and a cross-drive bundle path refused as a CdxError.
- [x] 5. Cover each behavior with a regression test and run full project validation.

# Validation
- `node bin/python-runner.js -m pytest test/test_profile_data_safety_py.py -q` -> 22 passed (5 new regression tests).
- `npm run lint` -> All checks passed.
- `npm test` -> 1011 passed.
- `cargo test --manifest-path tray/Cargo.toml` -> 96 passed; 0 failed.
- lint OK; 1011 Python tests; 96 Rust tests
- Finish workflow executed on 2026-09-06.
- Linked backlog/request close verification passed.

# AC Traceability
- request-AC1 -> This task. Proof: `src/session_service.py` `_discard_claude_credentials`, called from `remove_session` and from `copy_session` when a non-Claude source overwrites a Claude destination. Tests: `test_remove_deletes_the_profile_credential_and_frees_the_name`, `test_remove_reports_a_credential_that_could_not_be_deleted`, `test_copy_over_a_claude_destination_from_another_provider_leaves_no_credential`.
- request-AC2 -> This task. Proof: `src/claude_credentials.py` `peek_keychain_credentials` for the launch path in `src/provider_runtime.py`, and a deferred error in `src/claude_usage.py` `_read_claude_credentials` that only raises when no credential file answered. Test: `test_an_unusable_keychain_falls_back_to_credential_files`, with `test_keychain_errors_are_not_missing_and_never_leak_tokens` still holding req_070 AC3.
- request-AC3 -> This task. Proof: `src/claude_credentials.py` `_reject_custom_oauth` now guards `write_keychain_credentials` and `delete_keychain_credentials` only. Test: `test_a_custom_oauth_endpoint_blocks_writes_but_still_allows_reads`.
- request-AC4 -> This task. Proof: `copy_session` matches the `Keychains` entry by name and copies with `symlinks=True`; its failure path names a retained backup; `import_bundle` snapshots with `ignore_dangling_symlinks=True` and refuses a cross-drive path through `ValueError`. Covered by the existing copy/merge regression tests.
- request-AC5 -> This task. Proof: the commands recorded above.

# Report
- Delivered. Eight of the eleven review findings are fixed; the three left out are recorded as out of scope in `req_071` (operator-visible service name, native Security APIs for oversized credentials, keychain export portability).
- Finished on 2026-09-06.
- Linked backlog item(s): `item_145_post_review_hardening_of_profile_keychain_integration`
- Related request(s): `req_071_post_review_hardening_of_profile_keychain_integration`

# Links
- Request: `req_071_post_review_hardening_of_profile_keychain_integration`
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
