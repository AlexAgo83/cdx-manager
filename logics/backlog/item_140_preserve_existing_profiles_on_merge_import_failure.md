## item_140_preserve_existing_profiles_on_merge_import_failure - Preserve existing profiles on merge import failure
> From version: 0.20.8
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 90%
> Progress: 100%
> Complexity: High
> Theme: Profile data safety and authentication
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-06 11:55:44

# AI Context
- Summary: Merge failures call the destructive rollback helper without capturing the original profile or store record; an injected file write failure deletes both.
- Keywords: profile, data-safety, claude, keychain, regression
- Use when: Implementing this bounded slice and its failure-path checks.
- Skip when: Work belongs to a sibling slice or a new secret-store architecture.

# Problem
- Merge failures call the destructive rollback helper without capturing the original profile or store record; an injected file write failure deletes both.

# Scope
- In:
  - Trace import_bundle, _restore_import_backup, atomic_write, and store record/state writes before choosing the smallest rollback change.
  - Preserve original files, metadata and state on file or store failures; track only newly introduced merge artifacts or use reversible staging without dereferencing external links.
  - Preserve current merge precedence, successful imports, and force-import behavior; keep any recovery backup when rollback itself fails.
- Out:
  - Whole-bundle transactions across multiple sessions.
  - Concurrent lifecycle-operation locking redesign or a new storage backend.

# Acceptance criteria
- AC1: Inject a missing-file write failure and a state/store failure during merge; original profile bytes, session record and state remain unchanged.
- AC2: A failure after one imported file was created removes only new merge artifacts; pre-existing files and directories survive.
- AC3: If recovery fails, preserve recoverable data and report failure rather than deleting the only backup.
- AC4: Successful merge precedence and force-import rollback tests still pass.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: An injected file/state write failure during merge leaves the original profile contents, record, and state intact.

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
- Rationale: No dependency. Implement first because a normal I/O failure can destroy the local profile.

# Notes
- Dependencies and order: No dependency. Implement first because a normal I/O failure can destroy the local profile.
- Verification: Use temporary stores and injected OSError at file/state writes. Assert original contents and records, not just the raised exception.
- Evidence is pending implementation; review reproductions are not proof of a fix.
- Task `task_079_orchestrate_profile_data_safety_and_claude_keychain_integration` was finished via `logics-manager flow finish task` on 2026-09-06.

# Implementation references
- `src/session_backup.py`
- `src/session_store.py`
- `src/fs_utils.py`
- `test/test_session_service_py.py`
- `test/test_commands_backup_py.py`

# Tasks
- `task_079_orchestrate_profile_data_safety_and_claude_keychain_integration`
