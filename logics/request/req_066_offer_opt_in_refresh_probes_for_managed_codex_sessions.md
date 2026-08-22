## req_066_offer_opt_in_refresh_probes_for_managed_codex_sessions - Offer opt-in refresh probes for managed Codex sessions
> From version: 0.20.3
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Authentication reliability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-22 14:35:09

# AI Context
- Summary: Define an explicit CDX-only Codex refresh probe that is safe for manual use or a user-owned scheduler.
- Keywords: offer, opt, refresh, probes, managed, codex, sessions
- Use when: A managed Codex profile may have stale OAuth credentials and needs validation without a model turn.
- Skip when: The request is to copy credentials between hosts, install a scheduler automatically, or authenticate another provider.

# Needs
- A copied Codex profile can retain an expired access token while another host has refreshed its local session.
- Users need one explicit CDX command to make a non-generation Codex authentication probe for one managed session or all managed Codex sessions.
- Users must be able to choose manual use or schedule that command themselves, without CDX silently installing a cron job or exposing credential material.

# Context
- Codex keeps access, refresh, and identity tokens in each profile auth.json and rotates the refresh token during a refresh.
- src/codex_usage.py already serializes access to a profile auth home so a status probe cannot race an interactive Codex session and invalidate its refresh token.
- The current CDX login-status probe can trust the presence of a local auth file, so it is not sufficient to prove an access token can be renewed or used.
- A refresh probe must use the existing Codex local app-server or usage path that performs no model generation, and must not send a user prompt, create an agent turn, or report secrets.

# Acceptance criteria
- AC1: CDX exposes a documented command that accepts one managed Codex session or all managed Codex sessions and performs a real non-generation authentication/usage probe under that session's CODEX_HOME.
- AC2: The command serializes refresh attempts with the existing per-profile auth lock and reports a locked active session without racing or modifying its credentials.
- AC3: Text and JSON results distinguish valid or refreshed, locked, login-required, unsupported, and operational-failure outcomes without printing tokens, token-derived values, account identifiers, prompts, or provider output.
- AC4: A successful probe does not launch a model, submit a prompt, or consume model-generation quota; failures that require a new interactive login are actionable and non-zero for automation.
- AC5: Documentation includes one manual invocation and one clearly opt-in scheduler example, explains that hosts keep independent rotating credentials, and states that CDX does not create a scheduler automatically.
- AC6: Focused command, locking, result-contract, and documentation checks pass.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_050_opt_in_codex_authentication_refresh_probes`
- Architecture decision(s): (none yet)

# References
- README.md
- src/codex_usage.py
- src/provider_runtime.py
- src/cli_args.py
- src/commands/status.py
- src/commands/maintenance.py
- test/

# Backlog
- `item_133_add_a_locked_non_generation_codex_auth_refresh_command`
- `item_134_document_manual_and_scheduler_controlled_credential_maintenance`
