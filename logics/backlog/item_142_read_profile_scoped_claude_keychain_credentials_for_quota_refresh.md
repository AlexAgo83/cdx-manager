## item_142_read_profile_scoped_claude_keychain_credentials_for_quota_refresh - Read profile scoped Claude keychain credentials for quota refresh
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
- Summary: Quota refresh runs claude auth status but then reads only credential files, so keychain-only logins silently produce no quota probe.
- Keywords: profile, data-safety, claude, keychain, regression
- Use when: Implementing this bounded slice and its failure-path checks.
- Skip when: Work belongs to a sibling slice or a new secret-store architecture.

# Problem
- Quota refresh runs claude auth status but then reads only credential files, so keychain-only logins silently produce no quota probe.

# Scope
- In:
  - Verify the installed Claude service-name derivation, account selector, credential JSON shape and precedence using local provider code or a disposable synthetic entry; record the observed provider version.
  - Add the minimum shared profile-scoped credential resolution needed by usage, copy, export classification and rename. Reuse the repository's token validation and file readers.
  - Match provider precedence when keychain and legacy files disagree; never silently select another profile or the global Claude credential.
  - Bound keychain subprocess timeouts and preserve distinctions between absent credentials, inaccessible storage, malformed data and provider authentication failure.
  - Continue using the existing quota request path; do not add another generation request, refresh-token rotation, scheduler or background worker.
- Out:
  - A generic pluggable secret-store framework.
  - Reading all keychain entries or dumping provider responses/tokens.
  - Changing quota pricing, ranking policy, or adding a new provider backend.

# Acceptance criteria
- AC1: With only a valid profile-scoped keychain entry, the quota path calls its existing probe with that profile credential and records the returned quota.
- AC2: Distinct profiles never resolve one another's or the default global entry; a stale legacy file cannot override the credential selected by Claude.
- AC3: Missing entry, locked/denied keychain, timeout, malformed JSON and expired token produce explicit safe handling without a fresh fabricated status or secret output.
- AC4: Existing file-backed behavior on Linux/Windows remains intact and no macOS-only command runs there.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: AC3: A successful keychain-only authentication can supply the quota refresh path without requiring a plaintext credential file; missing and inaccessible credentials remain distinguishable from fresh quota data.

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
- Rationale: After the two High-priority data-safety protections. The verified profile resolver enables the copy credential step, export preflight and rename migration.

# Notes
- Dependencies and order: After the two High-priority data-safety protections. The verified profile resolver enables the copy credential step, export preflight and rename migration.
- Verification: Mock the bounded keychain subprocess and existing quota probe. Include two profile credentials and a conflicting legacy file; synthetic tokens must never appear in captured text/JSON diagnostics.
- Evidence is pending implementation; review reproductions are not proof of a fix.
- Task `task_079_orchestrate_profile_data_safety_and_claude_keychain_integration` was finished via `logics-manager flow finish task` on 2026-09-06.

# Implementation references
- `src/claude_usage.py`
- `src/claude_refresh.py`
- `src/provider_runtime.py`
- `src/commands/status.py`
- `test/test_runtime_py.py`
- `test/test_commands_status_py.py`

# Tasks
- `task_079_orchestrate_profile_data_safety_and_claude_keychain_integration`
