## prod_018_executable_quota_routing - Executable quota routing
> Date: 2026-08-08
> Status: Proposed
> Related request: `req_028_turn_quota_awareness_from_advice_into_execution_across_accounts_and_providers`
> Related backlog: `item_063_add_budget_and_fallback_model_as_pinnable_launch_settings`, `item_064_anchor_resume_and_handoff_on_a_provider_native_session_identity`, `item_065_continue_a_headless_run_on_the_next_eligible_account_after_a_rate_limit`, `item_066_pass_unvalidated_provider_arguments_through_instead_of_mapping_every_flag`, `item_067_delegate_background_execution_to_the_provider_where_the_installed_cli_supports_it`
> Related task: `task_039_orchestrate_executable_quota_routing_across_accounts_and_providers`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.

# Overview
cdx already knows which of a user's accounts has quota. This turns that knowledge from a recommendation the user has to act on into execution cdx performs: budgets and fallbacks pinned per session, resume anchored to a provider-native session identity rather than to recency, and headless runs that survive a rate limit by moving to the next eligible account and carrying their context with them. Supporting it are an escape hatch for provider flags cdx does not model, and a decision to route to native background execution instead of deepening the in-house one.

# Goals
- Make a long unattended task survive hitting a rate limit, by moving it to an account that has quota instead of failing.
- Give resume and context handoff a stable provider-native identity to anchor on, instead of recency heuristics and transcript scraping.
- Let a user cap what a session may spend, and let a session fall back automatically when its model is unavailable.
- Stop the flag-mapping treadmill by providing one explicit, clearly-unvalidated passthrough instead of chasing every new provider flag.
- Spend cdx's effort on cross-account routing - the part no provider will ever solve - and delegate the parts providers now solve natively.

# Non-goals
- Changing anything about the ollama provider, including the overlap with `codex --oss --local-provider ollama`, which the maintainer deliberately keeps as-is.
- Removing or rewriting the existing in-house detached launcher, which works and stays as the fallback path.
- Validating passthrough arguments, or extending the machine-readable schema contract to cover them.
- Automatic failover for interactive launches; this request covers headless `cdx run` only.
- Reconciling cdx's own permission vocabulary with the providers' finer-grained tool and sandbox controls.

# Scope and guardrails
- In: scaffolded request, product, backlog, orchestration task, validation, and handoff context.
- Out: unrelated workflow docs and implementation of generated tasks.

# Key product decisions
- Use structured input as the source of truth for generated docs.
- Keep generated write paths local and repo-bounded.

# Success signals
- Generated docs pass lint and audit without broad manual rewrites.
- Context-pack output can be handed to an implementation agent directly.

# References
- Product back-reference: `req_028_turn_quota_awareness_from_advice_into_execution_across_accounts_and_providers`
- Task back-reference: `task_039_orchestrate_executable_quota_routing_across_accounts_and_providers`
