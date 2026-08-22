## req_067_review_findings_codex_authentication_observability - Review findings: Codex authentication observability
> From version: 0.20.4
> Schema version: 1.0
> Status: Obsolete
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: General
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-22 14:36:08

# AI Context
- Summary: Make scheduled Codex authentication checks distinguish actionable login loss from operational uncertainty and ignore intentionally inactive profiles.
- Keywords: review, findings, codex, authentication, observability
- Use when: Reviewing the safety and operator signal of Codex authentication probes.
- Skip when: Implementing a new provider, copying credentials between hosts, or installing a scheduler.

# Needs
- Reuse the safe authentication-failure classification currently limited to `src/commands/auth.py` so `cdx doctor` can distinguish a new interactive login from an app-server or provider failure without returning provider output.
- Make `cdx auth refresh all` skip disabled Codex sessions, so an intentionally retired profile does not cause a scheduled check to fail.
- Define an explicit scheduler outcome when every selected profile is `locked`; silence must not imply that a usable credential was verified.
- Consume or discard app-server stderr while a diagnostic waits for stdout, so provider diagnostics cannot deadlock on a filled stderr pipe.
- Exercise `cdx doctor --json` from the packed npm and wheel artifacts in CI, not only from the source checkout.

# Context
- `src/provider_runtime.py` now uses the app-server probe for `cdx doctor`, but reports every non-lock failure as the generic `rate_limits_read_failed`; `src/commands/auth.py` already safely recognizes `login_required` from that diagnostic.
- `src/commands/auth.py` selects every Codex session for the `all` target, irrespective of the session's enabled state. An intentionally unavailable profile therefore keeps a user-owned scheduled check in failure.
- `src/commands/auth.py` treats `locked` as non-failing. The observed user-owned Tower wrapper emits only on a non-zero exit, so it can be silent when no session was actually verified.
- `src/codex_usage.py` starts `codex app-server` with `stderr=subprocess.PIPE` but only has a reader for stdout. A sufficiently chatty provider process can block before returning the JSON-RPC response and be misreported as a timeout.
- `.github/workflows/ci.yml` runs `cdx doctor --json` only in the source-install Windows smoke; the packed npm and wheel jobs invoke only `--version` and `schema --json`.
- Review evidence: `npm test` passed 980 tests, `npm run lint` passed, and `npm audit --omit=dev --json` reported zero vulnerabilities.
- Existing task `task_076_orchestrate_opt_in_codex_authentication_refresh_probes` already covers the original opt-in command and documentation; this request records follow-up observability behavior only.

# Acceptance criteria
- AC1: `cdx doctor` gives an actionable, token-safe login-required result when the app-server rejects a refresh token and a distinct result for operational probe failures.
- AC2: `cdx auth refresh all` excludes disabled Codex sessions while an explicit named session remains probeable.
- AC3: The documented scheduler contract makes an all-locked result visibly indeterminate rather than silently successful.
- AC4: Focused result-contract tests cover login-required, failed, locked, disabled, and valid outcomes without exposing credential material.
- AC5: App-server diagnostics cannot block solely because stderr is written while stdout is awaited.
- AC6: CI installs each published package form and runs a non-destructive doctor smoke with controlled provider shims.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- `src/commands/auth.py`
- `src/provider_runtime.py`
- `src/codex_usage.py`
- `test/test_commands_auth_py.py`
- `.github/workflows/ci.yml`

# Backlog
- none

# Links
- Superseded by: `req_068_harden_codex_authentication_observability`
