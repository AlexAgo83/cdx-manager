## item_030_preserve_degraded_auth_semantics_on_provider_probe_timeout - Preserve degraded auth semantics on provider probe timeout
> From version: 0.10.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Operator workflow
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- A bounded auth probe timeout currently returns False, which callers interpret as logged out.
- Transient provider CLI hangs can therefore persist a false logout or block commands with a misleading authentication error.

# Scope
- In:
  - Represent auth probe outcomes distinctly enough to separate authenticated, logged-out, timed-out/degraded, and probe-error states.
  - Update launch/run/status/doctor paths so timeout is explicit and never persisted as logged_out.
  - Keep existing successful-auth and real logged-out behavior unchanged.
  - Add tests for doctor diagnostics, Claude auth refresh state updates, and launch/run handling when the probe times out.
- Out:
  - Changing provider CLI commands.
  - Adding background retry services.

# Acceptance criteria
- A `subprocess.TimeoutExpired` probe outcome is visible as unknown/degraded in JSON diagnostics.
- Claude auth refresh does not write `logged_out` when the probe timed out.
- Launch/run errors caused by timeout mention the probe timeout or degraded state rather than claiming the session is logged out.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: A `subprocess.TimeoutExpired` probe outcome is visible as unknown/degraded in JSON diagnostics.
- request-AC5 -> This backlog slice. Proof: Claude auth refresh does not write `logged_out` when the probe timed out.
- request-AC1 -> This backlog slice. Evidence needed: npm and PyPI publish workflows validate release checksums against the tagged GitHub Release asset for the release tag, not against a main-branch checksum file.
- request-AC2 -> This backlog slice. Evidence needed: The standalone Windows installer generates a valid `cdx.cmd` launcher path containing the installed version directory, and a regression test covers the generated script content.
- request-AC4 -> This backlog slice. Evidence needed: Import bundle profile validation rejects non-object profile entries with `CdxError` before any filesystem mutation, and tests cover the malformed-entry case.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_004_post_remediation_hardening_follow_up_2026_07`
- Architecture decision(s): (none yet)
- Request: `req_011_address_july_2026_post_remediation_review_follow_up_findings`
- Primary task(s): `task_022_orchestrate_post_remediation_hardening_follow_up`

# AI Context
- Summary: Preserve degraded auth semantics on provider probe timeout
- Keywords: scaffolded-backlog, preserve degraded auth semantics on provider probe timeout, implementation-ready
- Use when: Implementing the scaffolded slice for Preserve degraded auth semantics on provider probe timeout.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.

# Tasks
- `task_022_orchestrate_post_remediation_hardening_follow_up`

# Notes
- Task `task_022_orchestrate_post_remediation_hardening_follow_up` was finished via `logics-manager flow finish task` on 2026-07-18.
