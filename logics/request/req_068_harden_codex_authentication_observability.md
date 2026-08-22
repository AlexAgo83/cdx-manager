## req_068_harden_codex_authentication_observability - Harden Codex authentication observability
> From version: 0.20.4
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Authentication reliability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-22 14:15:42

# AI Context
- Summary: Turn authentication probe outcomes into reliable operator signals without changing how credentials are acquired.
- Keywords: harden, codex, authentication, observability
- Use when: A Codex authentication health check needs an actionable result for automation or diagnosis.
- Skip when: Adding scheduling infrastructure, synchronizing credentials, or changing the provider OAuth flow.

# Needs
- A live Codex probe can fail because interactive login is required or because the app-server itself is unavailable; operators need those safe outcomes distinguished without provider output or credentials.
- A deliberately disabled Codex session is not eligible for automatic work and must not make `cdx auth refresh all` fail.
- A scheduler receiving only locked outcomes has not verified any credential, so a silent success would misrepresent the fleet state.

# Context
- `src/commands/auth.py` already classifies safe login-required markers for the refresh command, while `src/provider_runtime.py` currently collapses an equivalent doctor probe failure into a generic error.
- The `all` target currently selects every Codex session regardless of enabled state; an explicit named target remains the correct operator escape hatch for an intentionally disabled profile.
- The per-profile lock in `src/codex_usage.py` prevents concurrent refresh-token rotation. A lock is not a provider failure, but it is also not evidence of a verified credential.
- The work is limited to CDX result contracts, documentation, and tests. It neither creates a scheduler nor copies credentials between hosts.

# Acceptance criteria
- AC1: `cdx doctor` reports a token-safe login-required outcome for an app-server response that indicates rejected authentication, and a distinct operational failure for other probe errors.
- AC2: `cdx auth refresh all` skips disabled Codex sessions; an explicit named refresh still reports the selected disabled session's outcome.
- AC3: A refresh result with no valid or failed probe because every selected session is locked is explicit and non-zero for automation, while a mixed valid-and-locked result remains successful.
- AC4: JSON and text contracts, documentation, and focused tests cover valid, login-required, operational failure, disabled, locked-only, and mixed locked outcomes without exposing credentials or provider output.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_051_truthful_codex_authentication_health_signals`
- Architecture decision(s): (none yet)

# References
- src/commands/auth.py
- src/provider_runtime.py
- src/codex_usage.py
- src/health.py
- test/test_commands_auth_py.py
- test/test_commands_maintenance_py.py
- README.md

# Backlog
- `item_135_classify_live_codex_diagnostic_failures_safely`
- `item_136_exclude_disabled_profiles_from_bulk_codex_refresh`
- `item_137_make_all_locked_bulk_refresh_results_explicit`
