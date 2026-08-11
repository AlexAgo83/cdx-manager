## prod_029_capacity_first_cdx_tray_menu - Capacity-first CDX tray menu
> Date: 2026-08-11
> Status: Proposed
> Related request: `req_040_keep_the_cdx_tray_menu_globally_ordered_by_remaining_capacity`
> Related backlog: `item_087_flatten_the_tray_session_menu_while_preserving_provider_context`
> Related task: `task_051_orchestrate_the_capacity_first_cdx_tray_session_menu`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.

# Overview
Show one stable, globally capacity-sorted session list in the CDX tray and retain provider context within each row.

# Goals
- Make the most constrained session the first actionable row regardless of provider.
- Keep every rendered row and its session action correctly bound as capacity changes.
- Preserve provider identification in an accessible, compact form.

# Non-goals
- No changes to quota collection, snapshot ranking rules, tray transport, alerts, or session-launch behavior.
- No new sorting control, user preference, custom grouping mode, provider filter, or additional dependency.
- No redesign of gauges, capacity thresholds, icon state, refresh timing, or notification history.

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
- Product back-reference: `req_040_keep_the_cdx_tray_menu_globally_ordered_by_remaining_capacity`
- Task back-reference: `task_051_orchestrate_the_capacity_first_cdx_tray_session_menu`
