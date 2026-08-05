## prod_007_reliable_next_ready_notification_shortcut - Reliable next-ready notification shortcut
> Date: 2026-08-05
> Status: Proposed
> Related request: `req_014_prevent_cdx_ready_from_failing_when_no_notification_can_be_scheduled`
> Related backlog: `item_034_handle_no_target_cdx_ready_scheduling_gracefully`
> Related task: `task_025_orchestrate_safe_cdx_ready_no_target_handling`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.

# Overview
Make the ready shortcut report an unschedulable state as a normal outcome.

# Goals
- Keep `cdx ready` safe and understandable for every status inventory.
- Preserve the existing notification and scheduler contracts where a target exists.

# Non-goals
- Changing reset selection policy or polling behavior.
- Adding new scheduler backends or persistent notification management.

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
- Product back-reference: `req_014_prevent_cdx_ready_from_failing_when_no_notification_can_be_scheduled`
- Task back-reference: `task_025_orchestrate_safe_cdx_ready_no_target_handling`
