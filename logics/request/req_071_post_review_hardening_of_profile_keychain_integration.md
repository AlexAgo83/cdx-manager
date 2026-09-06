## req_071_post_review_hardening_of_profile_keychain_integration - Post-review hardening of profile keychain integration
> From version: 0.20.9
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 95%
> Complexity: Medium
> Theme: Profile data safety and authentication
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-09-06 12:15:21

# AI Context
- Summary: Close the gaps a high-effort code review found in the req_070 keychain delivery before it ships.
- Keywords: keychain, remove, orphan, fallback, locked, oauth, copytree
- Use when: Reviewing or extending the profile-scoped Claude keychain integration.
- Skip when: Working on Codex or Antigravity credential handling.

# Needs
- The req_070 delivery introduced profile-scoped keychain credentials but left `cdx rm` unaware of them, and made three read paths hard-fail where they previously degraded. Both are operator-visible regressions that must not ship in 0.20.9.

# Context
- Findings come from a code review of `20ef9d1..HEAD` (1 high, 3 medium, 7 low).
- The high finding is a leak plus a lockout: a removed session's OAuth token stays in the login keychain, and the stale entry then makes `cdx cp`/`cdx ren` refuse the freed name, with no command to clear it.
- The medium findings share one root cause: `read_keychain_credentials` raises for a locked, denied or timed-out keychain, and three callers with a working file fallback treat that as fatal.
- req_070 AC3 stands: a keychain failure must never be reported as a logged-out profile. Falling back is only allowed when a credential file actually answers.
- Out of scope: exposing the keychain service name to operators, native Security APIs for oversized credentials, and keychain export portability.

# Acceptance criteria
- AC1: Removing a session deletes that profile's keychain credential and no other, frees the name for reuse, and reports a deletion failure without pretending the session survived.
- AC2: A keychain that cannot answer falls back to the profile's credential files for quota refresh and launch, and is reported as an error only when no file credential answers either.
- AC3: A custom Claude OAuth endpoint blocks keychain writes but no longer blocks reads, so unrelated flows keep working.
- AC4: The remaining low-severity findings that can fail unsafely are fixed: the copy guard cannot follow a keychain symlink, a retained destination profile is named, a dangling link cannot fail a merge snapshot, and a cross-drive bundle path is refused as a CdxError.
- AC5: Project lint, Python tests and Rust tests pass.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_053_safe_profile_operations_with_isolated_claude_keychain_authentication`
- Architecture decision(s): (none yet)

# References
- `src/claude_credentials.py`
- `src/session_service.py`
- `src/claude_usage.py`
- `test/test_profile_data_safety_py.py`

# Backlog
- `item_145_post_review_hardening_of_profile_keychain_integration`
