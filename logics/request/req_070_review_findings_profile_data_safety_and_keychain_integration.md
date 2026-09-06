## req_070_review_findings_profile_data_safety_and_keychain_integration - Review findings: profile data safety and keychain integration
> From version: 0.20.8
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 90%
> Complexity: High
> Theme: Profile data safety and authentication
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-09-06 12:25:53

# AI Context
- Summary: Review of 20ef9d1 found destructive merge rollback and incomplete integration of Claude profile keychain storage with copy, quota refresh, export, and rename.
- Keywords: review, findings, profile, data, safety, keychain, integration
- Use when: Evaluating follow-up work for profile data safety or macOS Claude credential handling.
- Skip when: Implementing unrelated CLI or tray presentation changes.

# Needs
- P1: Preserve existing profile files, session metadata, and state when an import in merge mode fails.
- P1: Prevent profile copies from following the new Library/Keychains link into the operator's system keychain directory.
- P2: Let quota refresh consume the profile's actual credential backend when Claude stores authentication only in the keychain.
- P2: Make auth-inclusive exports carry usable profile-scoped credentials, or explicitly report that those credentials cannot be exported.
- P2: Preserve profile-scoped keychain authentication when a session is renamed.
- The operator requested a ready-to-develop corpus on 2026-09-06. All five findings are now scoped for implementation; the original review evidence remains below.

# Context
- Reviewed commit: `20ef9d15173d6f90b34ad580b1cd1cc151424ad7`, on 2026-09-06. The working tree was initially clean.
- Reviewed the authentication and profile lifecycle paths in depth, with additional inspection of the session store, bundle encoding, update manager, tray extraction/actions, packaging, and CI. This is not an exhaustive security or cross-platform audit.
- Existing corpus: `logics-manager status` reported no open workflow docs; `logics-manager health --format json` reported zero issues. Searches for keychain/keyring found no captured integration work. The completed backlog document titled "Safe bundle import: pre-validation, credential guard, per-session rollback" addresses force-import rollback; the merge failure below is a remaining gap. It is historical context, not lineage for this request.

## Finding 1: Merge rollback destroys the existing session (P1)
- Evidence: `src/session_backup.py:270` initializes backups and old records to None; only force mode captures them at line 274. The exception handler at line 333 calls `_restore_import_backup` for merge mode too. That helper deletes the profile directory at line 154 and removes the session record at line 162 when no old record was supplied.
- Reproduced with a temporary store and profile containing a sentinel credential file: import a bundle with a missing destination file using `merge=True`, inject an OSError at `src.session_backup.atomic_write`, and catch it. Both the original sentinel and the store record are gone afterwards.
- Impact: an ordinary disk or permission failure can turn a supposedly preserving merge into permanent loss of the local profile, including credentials and history.
- Coverage gap: existing merge tests cover successful preservation and missing-file imports, but not a write failure after merge begins.

## Finding 2: Profile copy duplicates the linked system keychain (P1)
- Evidence: `src/claude_usage.py:96` creates the profile's Library/Keychains symlink. `src/session_service.py:548` calls `shutil.copytree(source_root, temp_root)` with its default link-following behavior.
- Reproduced using a fake external keychain directory containing a sentinel login.keychain-db, linked beneath a temporary Claude profile. `copy_session` creates a real destination directory containing the sentinel, rather than retaining a link or excluding the external store.
- Impact: `cdx cp` can copy unrelated system keychain database files into a session profile, or fail on unreadable files. These are database copies, not a demonstration of plaintext secret disclosure. The copied real directory also prevents `_link_macos_keychain` from installing the intended live link, since the resulting FileExistsError is silently ignored.
- No actual system keychain contents were read or copied during the reproduction.

## Finding 3: Keychain-only logins no longer refresh quotas (P2)
- Evidence: `src/claude_usage.py:52` reads only the profile-relative files ".claude/.credentials.json" and "credentials/default.json"; it never consults secure storage. `refresh_claude_session_status` runs the auth refresher, then returns None at line 329 if those files are absent.
- Reproduced with a temporary keychain-only profile and a completed no-op auth refresher: the result is None and the mocked rate-limit probe is never called. The earlier live local login inspection also found loggedIn=true and no `.credentials.json`, showing that this profile layout occurs after the fix; no real token was extracted.
- Impact: a successful login can coexist with missing or stale quota data in CDX, because the keychain fix moved credentials out of the only locations the quota reader understands. A successful auth-status check alone does not validate quota refresh.

## Finding 4: Auth export silently omits keychain credentials (P2)
- Evidence: `src/session_backup.py:58` defines a file-only credential allowlist; `_collect_auth_files` at line 76 skips absent files, and `export_bundle` still reports include_auth=true at line 215. There is no keychain export path.
- Reproduced with a temporary keychain-only profile containing `.claude.json` account metadata: the collector exports only that metadata and no credential. The enclosing export code encrypts the collected payload without checking whether authentication is actually portable.
- Impact: an `--include-auth` export can appear successful while restoring a profile on another machine still requires login. Existing file-backed export round trips do not exercise this backend.

## Finding 5: Rename loses the keychain lookup identity (P2)
- Evidence: `src/claude_usage.py:127` derives CLAUDE_SECURESTORAGE_CONFIG_DIR from authHome; this is also the keychain namespace described by that helper. `src/session_service.py:589` moves only the filesystem tree, and line 600 changes authHome without migrating a secure-storage entry.
- A temporary-store reproduction confirms rename changes the configuration path. The lost credential lookup follows from the documented path-based namespace and absence of migration; no live authenticated session was renamed during this review.
- Impact: a keychain-only Claude profile requests login after `cdx ren`, although the command is expected to move its authentication with the profile.

## Validation observed
- `rtk npm run lint`: passed, including project-doc checks, Ruff, JavaScript syntax, and Python compilation.
- `rtk npm test`: 989 Python tests passed in 22.21 seconds.
- `rtk cargo test --manifest-path tray/Cargo.toml`: 96 Rust tests passed.
- `rtk npm pack --dry-run`: passed.
- A temporary Python script using only stdlib fixtures/mocks and the repository functions reproduced findings 1-4 and checked the path change underlying finding 5. Reproductions operated on synthetic profiles in temporary directories; no provider generation or real credential extraction was needed.
- Linux/Windows execution and a full authenticated keychain export/rename round trip were not performed. Application source and existing tests are unchanged.

- AC4's "explicit unsupported export" decision was superseded by `req_072_keychain_credential_portability_and_operator_recovery` before 0.20.9 shipped: the credential is now portable.

# Acceptance criteria
- AC1: An injected file/state write failure during merge leaves the original profile contents, record, and state intact.
- AC2: Copying a profile with an external keychain symlink never duplicates that directory's contents and leaves credential storage resolvable for the copied profile.
- AC3: A successful keychain-only authentication can supply the quota refresh path without requiring a plaintext credential file; missing and inaccessible credentials remain distinguishable from fresh quota data.
- AC4: Auth-inclusive export/import preserves a keychain-only profile's authentication across distinct profile roots, or explicitly reports unsupported credential portability instead of silently claiming success.
- AC5: Renaming a keychain-only profile preserves authentication under the new profile identity and keeps other profiles isolated.
- AC6: Any selected fixes add focused regression coverage for the corresponding failing scenarios; the current Python/Rust suites and lint continue to pass.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Delivery decisions
- Implement data-preserving merge rollback and copy link protection first. Credential resolution enables isolated credential copy, quota refresh and rename.
- AC4 uses explicit unsupported-export refusal for keychain-only credentials, before any output file is replaced. Full keychain credential portability and bundle format changes are deferred.
- The orchestration task implements the linked slices and owns final validation; no further task scaffolding is needed to begin.
- Verify the installed provider namespace and precedence with synthetic evidence before implementing keychain operations. Tests use fake credentials and temporary profiles, not the operator's live sessions.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- `src/session_backup.py`
- `src/session_service.py`
- `src/claude_usage.py`
- `src/provider_runtime.py`
- `test/test_session_service_py.py`
- `test/test_runtime_py.py`

# Backlog
- `item_140_preserve_existing_profiles_on_merge_import_failure`
- `item_141_copy_claude_profiles_without_traversing_the_system_keychain`
- `item_142_read_profile_scoped_claude_keychain_credentials_for_quota_refresh`
- `item_143_report_unsupported_keychain_credential_exports_explicitly`
- `item_144_preserve_claude_keychain_authentication_across_session_rename`
