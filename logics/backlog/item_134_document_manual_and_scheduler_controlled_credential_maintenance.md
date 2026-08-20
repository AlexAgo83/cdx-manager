## item_134_document_manual_and_scheduler_controlled_credential_maintenance - Document manual and scheduler-controlled credential maintenance
> From version: 0.20.3
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Low
> Theme: Authentication reliability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-20 11:29:03

# AI Context
- Summary: Document manual and opt-in scheduled operation without making CDX own host scheduling.
- Keywords: document, manual, scheduler, controlled, credential, maintenance
- Use when: Writing command help and documentation for safe credential maintenance and its login fallback.
- Skip when: Provisioning a cron service, embedding credentials, or documenting real operator accounts or hosts.

# Problem
- Operators need a predictable manual remedy and may want a scheduler, but automatic background mutation would be surprising and can contend with active sessions.
- A copied profile is not a live credential replication channel once provider refresh-token rotation occurs.

# Scope
- In:
  - Document manual invocation, safe result meanings, the interactive-login fallback, and an opt-in scheduler example based on JSON and exit status.
  - State that the command makes no model-generation request and that CDX never creates or enables a scheduler on behalf of the user.
  - Explain the independent-host and rotating-refresh-token boundary concisely without prescribing auth-file copying.
- Out:
  - Provisioning a system scheduler, deploying host configuration, or managing scheduler credentials.
  - Publishing real host names, account names, organization names, or credential examples.

# Acceptance criteria
- AC1: README and command help show a manual single-session and all-session invocation.
- AC2: Documentation supplies one opt-in scheduler example and makes clear that the user owns its installation and cadence.
- AC3: Documentation says that login-required needs an interactive cdx login and never suggests exposing tokens in a scheduler.
- AC4: Documentation checks and focused command-contract tests pass.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: AC1: README and command help show a manual single-session and all-session invocation.
- request-AC4 -> This backlog slice. Proof: AC2: Documentation supplies one opt-in scheduler example and makes clear that the user owns its installation and cadence.
- request-AC5 -> This backlog slice. Proof: AC3: Documentation says that login-required needs an interactive cdx login and never suggests exposing tokens in a scheduler.
- request-AC6 -> This backlog slice. Proof: AC4: Documentation checks and focused command-contract tests pass.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_050_opt_in_codex_authentication_refresh_probes`
- Architecture decision(s): (none yet)
- Request: `req_066_offer_opt_in_refresh_probes_for_managed_codex_sessions`
- Primary task(s): `task_076_orchestrate_opt_in_codex_authentication_refresh_probes`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.
