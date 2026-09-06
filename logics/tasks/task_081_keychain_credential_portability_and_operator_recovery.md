## task_081_keychain_credential_portability_and_operator_recovery - Keychain credential portability and operator recovery
> From version: 0.20.9
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 95%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-09-06 12:25:44

# AI Context
- Summary: Deliver keychain portability and the two recovery messages, reversing the req_070 export refusal.
- Keywords: keychain, credential, portability, operator, recovery
- Use when: Working on bundle authentication or keychain error messages.
- Skip when: Working on Codex or Antigravity credential handling.

# Definition of Done (DoD)
- [x] The backlog scope is implemented.
- [x] Acceptance criteria are covered.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# Backlog
- `item_146_keychain_credential_portability_and_operator_recovery`

# Acceptance criteria
- AC1: `cdx export --include-auth` includes a keychain-backed profile's credential, and `cdx import` restores a login that works.
- AC2: An import that carries a credential clears any keychain entry the destination profile already had, so the imported credential is the one in effect.
- AC3: The keychain wins over a stale credential file when both exist on export.
- AC4: A keychain that cannot be read is still an explicit error, in text and JSON, before anything is written.
- AC5: Refusing an orphan destination entry names the command that clears it, and an oversized credential error states that nothing changed and what to do instead.
- AC6: Operator documentation matches the new behavior.

# Plan
- [x] 1. Export the keychain entry under the credential path Claude Code already uses, so the bundle schema is unchanged.
- [x] 2. Drop the export refusal and keep the unreadable-keychain error, before anything is written.
- [x] 3. Clear a destination keychain entry when an import carries a credential for that profile.
- [x] 4. Name the clearing command in the orphan-entry refusal, and say what to do instead when a credential is too large to transfer.
- [x] 5. Replace the refusal tests with portability tests, keep the text/JSON CLI contract covered, and update README and changelog.

# Validation
- `node bin/python-runner.js -m pytest test/test_profile_data_safety_py.py -q` -> 23 passed.
- `npm run lint` -> All checks passed.
- `npm test` -> 1012 passed.
- `cargo test --manifest-path tray/Cargo.toml` -> 96 passed; 0 failed.
- lint OK; 1012 Python tests; 96 Rust tests
- Finish workflow executed on 2026-09-06.
- Linked backlog/request close verification passed.

# AC Traceability
- request-AC1 -> This task. Proof: `src/session_backup.py` `_collect_auth_files` emits the keychain entry under `CLAUDE_CREDENTIALS_BUNDLE_PATH`. Test: `test_export_carries_the_keychain_credential_and_import_makes_it_the_live_one`.
- request-AC2 -> This task. Proof: `import_bundle` calls `delete_keychain_credentials` when that path was written for a Claude profile. Test: same, second half.
- request-AC3 -> This task. Proof: the keychain entry replaces the file content for that path when both exist. Test: `test_export_prefers_the_keychain_over_a_stale_credential_file`.
- request-AC4 -> This task. Proof: `export_bundle` wraps a `CdxError` from collection as "Cannot export authentication for <name>. Nothing was exported." before `atomic_write`. Tests: `test_export_failure_has_nonzero_text_and_json_cli_outcomes`, `test_export_denied_keychain_never_replaces_output`.
- request-AC5 -> This task. Proof: `src/claude_credentials.py` names the service in the overwrite refusal and states the alternative in the size error.
- request-AC6 -> This task. Proof: README export notes and `changelogs/CHANGELOGS_0_20_9.md` describe portability, the destination-entry replacement and the credential-file landing spot.

# Report
- Delivered. Every review finding from the req_070 delivery is now either fixed or, for native Security APIs, bounded by an error that tells the operator what to do instead.
- Finished on 2026-09-06.
- Linked backlog item(s): `item_146_keychain_credential_portability_and_operator_recovery`
- Related request(s): `req_072_keychain_credential_portability_and_operator_recovery`

# Links
- Request: `req_072_keychain_credential_portability_and_operator_recovery`
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
