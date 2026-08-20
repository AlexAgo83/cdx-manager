## item_133_add_a_locked_non_generation_codex_auth_refresh_command - Add a locked non-generation Codex auth refresh command
> From version: 0.20.3
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 90%
> Complexity: Medium
> Theme: Authentication reliability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-20 11:54:32

# AI Context
- Summary: Add the one-or-all Codex command at the existing locked provider-native refresh boundary.
- Keywords: add, locked, non, generation, codex, auth, refresh, command
- Use when: Implementing safe results and exit semantics for an explicit Codex credential refresh probe.
- Skip when: Building OAuth itself, starting an agent, or expanding the operation to other providers.

# Problem
- A local auth-file check can report a session as authenticated after its access token has expired.
- Concurrent refreshes can rotate a profile refresh token underneath an active interactive session.

# Scope
- In:
  - Add the smallest CLI surface for one named Codex session and an explicit all-managed-Codex selection.
  - Reuse the current per-CODEX_HOME lock and provider-native non-generation app-server or usage request.
  - Return stable per-session text, JSON, and exit-status outcomes for valid/refreshed, locked, login-required, unsupported, and operational failure.
  - Add focused tests for selection, no prompt/model invocation, lock contention, safe result serialization, and automation failure semantics.
- Out:
  - Reimplementing OAuth, decoding or displaying token values, or writing a second credential store.
  - Probing Claude, other providers, or sessions CDX does not manage.
  - Changing ordinary cdx status semantics beyond shared safe helpers required by this command.

# Acceptance criteria
- AC1: One managed Codex session and the explicit all selection route to the same locked provider-native probe.
- AC2: A lock held by an active session returns a distinct non-destructive result and does not call the provider probe.
- AC3: A rejected or expired refresh token returns login-required with a direct cdx login remedy and an automation-visible failure status.
- AC4: JSON output contains only session, provider, outcome, and safe diagnostic fields.
- AC5: Focused tests prove no model prompt or agent-run path is invoked.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: One managed Codex session and the explicit all selection route to the same locked provider-native probe.
- request-AC2 -> This backlog slice. Proof: AC2: A lock held by an active session returns a distinct non-destructive result and does not call the provider probe.
- request-AC3 -> This backlog slice. Proof: AC3: A rejected or expired refresh token returns login-required with a direct cdx login remedy and an automation-visible failure status.
- request-AC4 -> This backlog slice. Proof: AC4: JSON output contains only session, provider, outcome, and safe diagnostic fields.
- request-AC6 -> This backlog slice. Proof: AC5: Focused tests prove no model prompt or agent-run path is invoked.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_050_opt_in_codex_authentication_refresh_probes`
- Architecture decision(s): (none yet)
- Request: `req_066_offer_opt_in_refresh_probes_for_managed_codex_sessions`
- Primary task(s): `task_076_orchestrate_opt_in_codex_authentication_refresh_probes`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
