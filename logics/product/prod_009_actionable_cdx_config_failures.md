## prod_009_actionable_cdx_config_failures - Actionable cdx config failures
> Date: 2026-08-05
> Status: Proposed
> Related request: `req_016_clarify_cdx_config_errors_for_unknown_sessions`
> Related backlog: `item_036_improve_unknown_session_guidance_for_cdx_config`
> Related task: `task_027_orchestrate_actionable_cdx_config_error_guidance`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.

# Overview
Make a missing config target easy to diagnose and recover from.

# Goals
- Give a concrete next command in the config failure path.
- Preserve the established API error classification.

# Non-goals
- Renaming sessions, adding interactive selection, changing session storage, or rewriting unrelated unknown-session messages.

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
- Product back-reference: `req_016_clarify_cdx_config_errors_for_unknown_sessions`
- Task back-reference: `task_027_orchestrate_actionable_cdx_config_error_guidance`
