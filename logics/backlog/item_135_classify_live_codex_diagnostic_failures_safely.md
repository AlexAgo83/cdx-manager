## item_135_classify_live_codex_diagnostic_failures_safely - Classify live Codex diagnostic failures safely
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
- Summary: Share the existing safe authentication classifier so doctor distinguishes a required login from a probe failure.
- Keywords: classify, live, codex, diagnostic, failures, safely
- Use when: An app-server diagnostic must remain actionable without returning provider output.
- Skip when: Changing login flows or exposing response payloads.

# Problem
- Doctor currently cannot distinguish a rejected refresh token from a generic app-server probe failure.

# Scope
- In:
  - Reuse one token-safe classification path for refresh and doctor diagnostics.
  - Add focused result-contract coverage and concise user guidance.
- Out:
  - Returning raw provider responses or credentials.
  - Changing provider authentication flows.

# Acceptance criteria
- AC1: Doctor reports login-required only for the established safe auth markers and preserves a separate operational error otherwise.
- AC2: The diagnostic payload contains no raw provider response or credential material.
- AC3: Focused tests cover both failure categories and the project validation suite passes.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: Doctor reports login-required only for the established safe auth markers and preserves a separate operational error otherwise.
- request-AC4 -> This backlog slice. Proof: AC2: The diagnostic payload contains no raw provider response or credential material.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_051_truthful_codex_authentication_health_signals`
- Architecture decision(s): (none yet)
- Request: `req_068_harden_codex_authentication_observability`
- Primary task(s): `task_077_orchestrate_truthful_codex_authentication_health_signals`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.

# Tasks
- `task_077_orchestrate_truthful_codex_authentication_health_signals`

# Notes
- Task `task_077_orchestrate_truthful_codex_authentication_health_signals` was finished via `logics-manager flow finish task` on 2026-08-22.
