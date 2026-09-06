## item_145_post_review_hardening_of_profile_keychain_integration - Post-review hardening of profile keychain integration
> From version: 0.20.9
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 95%
> Progress: 100%
> Complexity: High
> Theme: Operator workflow and runtime integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-06 12:15:22

# AI Context
- Summary: Fix the review findings on the req_070 keychain delivery: rm leaves the credential behind, and three read paths hard-fail on an unusable keychain.
- Keywords: post, review, hardening, profile, keychain, integration
- Use when: Touching profile removal, copy, rename or Claude credential resolution.
- Skip when: Working on Codex or Antigravity credential handling.

# Problem
The req_070 delivery introduced profile-scoped keychain credentials but left `cdx rm` unaware of them, and made three read paths hard-fail where they previously degraded. Both are operator-visible regressions that must not ship in 0.20.9.

# Scope
- In:
  - credential cleanup on session removal and on cross-provider overwrite
  - read-path fallback for an unusable keychain, in quota refresh and launch
  - the custom-OAuth guard moved to writes only
  - the fail-safe fixes among the low findings
- Out:
  - exposing the keychain service name to operators
  - native Security APIs for oversized credentials
  - keychain export portability

# Acceptance criteria
- AC1: Removing a session deletes that profile's keychain credential and no other, frees the name for reuse, and reports a deletion failure without pretending the session survived.
- AC2: A keychain that cannot answer falls back to the profile's credential files for quota refresh and launch, and is reported as an error only when no file credential answers either.
- AC3: A custom Claude OAuth endpoint blocks keychain writes but no longer blocks reads, so unrelated flows keep working.
- AC4: The remaining low-severity findings that can fail unsafely are fixed: the copy guard cannot follow a keychain symlink, a retained destination profile is named, a dangling link cannot fail a merge snapshot, and a cross-drive bundle path is refused as a CdxError.
- AC5: Project lint, Python tests and Rust tests pass.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Removing a session deletes that profile's keychain credential and no other, frees the name for reuse, and reports a deletion failure without pretending the session survived.
- request-AC2 -> This backlog slice. Proof: AC2: A keychain that cannot answer falls back to the profile's credential files for quota refresh and launch, and is reported as an error only when no file credential answers either.
- request-AC3 -> This backlog slice. Proof: AC3: A custom Claude OAuth endpoint blocks keychain writes but no longer blocks reads, so unrelated flows keep working.
- request-AC4 -> This backlog slice. Proof: AC4: The remaining low-severity findings that can fail unsafely are fixed: the copy guard cannot follow a keychain symlink, a retained destination profile is named, a dangling link cannot fail a merge snapshot, and a cross-drive bundle path is refused as a CdxError.
- request-AC5 -> This backlog slice. Proof: AC5: Project lint, Python tests and Rust tests pass.

# Decision framing
- Product framing: Not needed
- Product signals: (none detected)
- Product follow-up: No product brief follow-up is expected based on current signals.
- Architecture framing: Not needed
- Architecture signals: (none detected)
- Architecture follow-up: No architecture decision follow-up is expected based on current signals.

# Links
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
- Request: `req_071_post_review_hardening_of_profile_keychain_integration`
- Primary task(s): `task_080_post_review_hardening_of_profile_keychain_integration`

# Priority
- Priority: High
- Rationale: A token left in the keychain and three hard-failing read paths would ship in 0.20.9 otherwise.

# Notes
- Hybrid rationale: Derived from request `req_071_post_review_hardening_of_profile_keychain_integration` and kept bounded to one coherent delivery slice.
- Source file: `logics/request/req_071_post_review_hardening_of_profile_keychain_integration.md`.
- Generated locally by logics-manager.
- Task `task_080_post_review_hardening_of_profile_keychain_integration` was finished via `logics-manager flow finish task` on 2026-09-06.

# Tasks
- `task_080_post_review_hardening_of_profile_keychain_integration`
