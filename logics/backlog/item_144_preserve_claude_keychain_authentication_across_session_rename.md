## item_144_preserve_claude_keychain_authentication_across_session_rename - Preserve Claude keychain authentication across session rename
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
- Summary: Renaming a Claude profile changes authHome and therefore the secure-storage namespace, but currently migrates only the filesystem tree and store record.
- Keywords: profile, data-safety, claude, keychain, regression
- Use when: Implementing this bounded slice and its failure-path checks.
- Skip when: Work belongs to a sibling slice or a new secret-store architecture.

# Problem
- Renaming a Claude profile changes authHome and therefore the secure-storage namespace, but currently migrates only the filesystem tree and store record.

# Scope
- In:
  - Use the verified provider namespace and profile-scoped credential operations to migrate only the renamed profile's credential.
  - Write and verify the destination credential before removing the source; keep the source recoverable through filesystem and store commit failures.
  - Never overwrite an unrelated destination keychain entry silently. Preserve current file-backed rename behavior and the global/default entry.
  - On cleanup failure after a committed rename, keep the working destination and report the precise partial cleanup outcome.
  - Own final cross-slice validation evidence for request AC6; each earlier slice still supplies its own regression checks.
- Out:
  - Changing all credential namespaces or adding permanent alias registries.
  - Deleting global or unrelated entries, or renaming the operator's live profile during automated tests.
  - Expanding this request into logout/remove credential lifecycle redesign.

# Acceptance criteria
- AC1: A synthetic keychain-only profile remains authenticated after rename under the destination namespace; other profiles and the global entry remain unchanged.
- AC2: Destination-write, verification, directory-move and store-save failures preserve the original usable profile/credential and undo only entries created by this attempt.
- AC3: Destination entry collisions are refused before destructive mutation; source cleanup failure leaves the committed destination usable and reports the remaining old entry.
- AC4: Record focused regression evidence across all five slices and passing project lint, Python tests, Rust tests and npm packaging dry-run. Do not substitute auth-status success for quota/export/rename coverage.

# AC Traceability
- request-AC5 -> This backlog slice. Proof: AC5: Renaming a keychain-only profile preserves authentication under the new profile identity and keeps other profiles isolated.
- request-AC6 -> This backlog slice. Proof: AC6: Any selected fixes add focused regression coverage for the corresponding failing scenarios; the current Python/Rust suites and lint continue to pass.

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
- Rationale: After the profile credential resolver and copy credential semantics. Final regression run follows all slices; no production credential mutation is needed for automated proof.

# Notes
- Dependencies and order: After the profile credential resolver and copy credential semantics. Final regression run follows all slices; no production credential mutation is needed for automated proof.
- Verification: Use an in-memory fake keychain plus real temporary directories/store. Inject each failure boundary and assert both credential identity and filesystem/store state.
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
