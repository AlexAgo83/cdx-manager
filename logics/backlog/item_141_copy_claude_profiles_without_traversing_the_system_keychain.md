## item_141_copy_claude_profiles_without_traversing_the_system_keychain - Copy Claude profiles without traversing the system keychain
> From version: 0.20.8
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 90%
> Progress: 100%
> Complexity: Medium
> Theme: Profile data safety and authentication
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-06 11:55:44

# AI Context
- Summary: copy_session uses copytree with default link dereferencing; the new Library/Keychains symlink causes system keychain database contents to be copied into a profile.
- Keywords: profile, data-safety, claude, keychain, regression
- Use when: Implementing this bounded slice and its failure-path checks.
- Skip when: Work belongs to a sibling slice or a new secret-store architecture.

# Problem
- copy_session uses copytree with default link dereferencing; the new Library/Keychains symlink causes system keychain database contents to be copied into a profile.

# Scope
- In:
  - Prevent traversal of the managed Library/Keychains link during staging; preserve or recreate the link without changing unrelated profile-copy semantics.
  - Keep source and destination credential namespaces isolated. Copy only the source profile credential into the destination namespace when needed, never the system keychain directory.
  - Reuse the bounded profile credential resolver delivered by the quota slice for the credential-copy portion. Land the non-traversal protection first.
  - Keep destination overwrite and failure rollback behavior, including any pre-existing destination credential, consistent with filesystem/store rollback.
- Out:
  - Blindly deleting an existing real Library/Keychains directory or assuming it is disposable.
  - Copying global keychain entries, weakening keychain access controls, or redesigning all filesystem symlinks.

# Acceptance criteria
- AC1: A fake linked keychain with an external sentinel is never traversed or copied, including when reading that sentinel would fail.
- AC2: The copied profile resolves the intended live keychain, uses its own namespace, and can authenticate using only the source profile credential.
- AC3: An injected copy, credential-write or record-save failure preserves the original source and any existing destination profile and credential.
- AC4: Unrelated profile files and established overwrite behavior remain covered by the existing copy tests.

# AC Traceability
- request-AC2 -> This backlog slice. Proof: AC2: Copying a profile with an external keychain symlink never duplicates that directory's contents and leaves credential storage resolvable for the copied profile.

# Decision framing
- Product framing: Required; this slice changes the promises made about profile safety or credential availability.
- Architecture framing: Use existing domain modules and the smallest shared profile credential operations. No new backend framework or package is required.

# Links
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
- Request: `req_070_review_findings_profile_data_safety_and_keychain_integration`
- Primary task(s): `task_079_orchestrate_profile_data_safety_and_claude_keychain_integration`

# Priority
- Priority: High
- Rationale: Start link-traversal protection immediately after merge rollback. Complete credential-copy integration after the profile credential resolver is available; do not let this dependency delay the High-priority protection.

# Notes
- Dependencies and order: Start link-traversal protection immediately after merge rollback. Complete credential-copy integration after the profile credential resolver is available; do not let this dependency delay the High-priority protection.
- Verification: Use a fake keychain directory and an in-memory credential store with two distinct profile entries; do not read the real operator keychain.
- Evidence is pending implementation; review reproductions are not proof of a fix.
- Task `task_079_orchestrate_profile_data_safety_and_claude_keychain_integration` was finished via `logics-manager flow finish task` on 2026-09-06.

# Implementation references
- `src/session_service.py`
- `src/claude_usage.py`
- `src/provider_runtime.py`
- `test/test_session_service_py.py`
- `test/test_runtime_py.py`

# Tasks
- `task_079_orchestrate_profile_data_safety_and_claude_keychain_integration`
