## item_143_report_unsupported_keychain_credential_exports_explicitly - Report unsupported keychain credential exports explicitly
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
- Summary: The auth exporter collects only files and still claims include_auth=true when a keychain-only profile contributes account metadata but no portable credential.
- Keywords: profile, data-safety, claude, keychain, regression
- Use when: Implementing this bounded slice and its failure-path checks.
- Skip when: Work belongs to a sibling slice or a new secret-store architecture.

# Problem
- The auth exporter collects only files and still claims include_auth=true when a keychain-only profile contributes account metadata but no portable credential.

# Scope
- In:
  - Choose the explicit-unsupported branch already allowed by request AC4: refuse the entire --include-auth export if any selected authenticated profile relies on unsupported keychain-only credentials.
  - Perform the profile-scoped preflight before any destination replacement, including --force; return non-zero in text and JSON with affected session names and a token-safe reason.
  - Explain that metadata-only export remains available and the imported profile will need login. Preserve file-backed encrypted export/import and the existing bundle format.
  - Treat denied or unavailable credential storage as an explicit failure, not as proof the profile is unauthenticated.
- Out:
  - Keychain secret serialization, a new bundle schema, or cross-host credential migration.
  - Silently writing a partial auth bundle or automatically falling back to plaintext credential storage.

# Acceptance criteria
- AC1: A keychain-only profile makes --include-auth fail before writing a bundle; metadata presence does not count as exported authentication.
- AC2: For a mixed selection or --force, refusal preserves the existing destination bytes and reports affected profile names without secrets in text/JSON.
- AC3: File-backed auth export/import round trips and metadata-only exports remain successful; documentation states the unsupported keychain portability limit.
- AC4: Denied storage produces a safe diagnostic rather than a successful incomplete bundle.

# AC Traceability
- request-AC4 -> This backlog slice. Proof: AC4: Auth-inclusive export/import preserves a keychain-only profile's authentication across distinct profile roots, or explicitly reports unsupported credential portability instead of silently claiming success.

# Decision framing
- Product framing: Required; this slice changes the promises made about profile safety or credential availability.
- Architecture framing: Use existing domain modules and the smallest shared profile credential operations. No new backend framework or package is required.

# Links
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
- Request: `req_070_review_findings_profile_data_safety_and_keychain_integration`
- Primary task(s): `task_079_orchestrate_profile_data_safety_and_claude_keychain_integration`

# Priority
- Priority: Medium
- Rationale: After the profile-scoped resolver. Uses the explicit unsupported option from the request; full credential portability is intentionally deferred.

# Notes
- Dependencies and order: After the profile-scoped resolver. Uses the explicit unsupported option from the request; full credential portability is intentionally deferred.
- Verification: Test text/JSON exit status, mixed profiles and unchanged pre-existing output on refusal using synthetic credential lookup results.
- Evidence is pending implementation; review reproductions are not proof of a fix.
- Task `task_079_orchestrate_profile_data_safety_and_claude_keychain_integration` was finished via `logics-manager flow finish task` on 2026-09-06.

# Implementation references
- `src/session_backup.py`
- `src/commands/backup.py`
- `src/cli_helpers.py`
- `test/test_commands_backup_py.py`
- `test/test_session_service_py.py`
- `README.md`

# Tasks
- `task_079_orchestrate_profile_data_safety_and_claude_keychain_integration`
