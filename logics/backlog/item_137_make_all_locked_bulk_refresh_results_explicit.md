## item_137_make_all_locked_bulk_refresh_results_explicit - Make all-locked bulk refresh results explicit
> From version: 0.20.4
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Low
> Theme: Authentication reliability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-22 14:15:43

# AI Context
- Summary: Make a bulk probe that verifies no profile because all locks are held explicit to automation.
- Keywords: all, locked, bulk, refresh, results, explicit
- Use when: A scheduler needs an honest result from a lock-protected bulk probe.
- Skip when: Waiting for locks, terminating sessions, or bypassing concurrency protection.

# Problem
- A bulk probe with only locked sessions exits successfully even though it verified no credential.

# Scope
- In:
  - Define the smallest explicit non-success outcome for an all-locked selection.
  - Preserve success when at least one selected profile was verified and none failed.
- Out:
  - Waiting for locks, killing active sessions, or bypassing the refresh lock.

# Acceptance criteria
- AC1: An all-locked bulk refresh is visible to JSON, text, and exit-code consumers.
- AC2: A valid-and-locked mixed result remains successful.
- AC3: Documentation explains the scheduler consequence and focused tests cover both cases.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: AC1: An all-locked bulk refresh is visible to JSON, text, and exit-code consumers.
- request-AC4 -> This backlog slice. Proof: AC2: A valid-and-locked mixed result remains successful.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_051_truthful_codex_authentication_health_signals`
- Architecture decision(s): (none yet)
- Request: `req_068_harden_codex_authentication_observability`
- Primary task(s): `task_077_orchestrate_truthful_codex_authentication_health_signals`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.

# Tasks
- `task_077_orchestrate_truthful_codex_authentication_health_signals`

# Notes
- Task `task_077_orchestrate_truthful_codex_authentication_health_signals` was finished via `logics-manager flow finish task` on 2026-08-22.
