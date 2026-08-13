## prod_045_repository_oriented_logics_tray_navigation - Repository-oriented Logics tray navigation
> Date: 2026-08-13
> Status: Settled
> Related request: `req_058_group_logics_tray_next_actions_by_repository`
> Related backlog: `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`
> Related task: `task_069_orchestrate_repository_grouped_logics_tray_navigation`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.
> Indicators reviewed: 2026-08-13 01:57:07

# Overview
Turn the Logics section of the tray from one global next-action row into a compact repository menu, so an operator can see and open the next work in each active repository without leaving the tray.

```mermaid
flowchart LR
  Roots[Repository roots] --> Groups[Bounded card groups]
  Groups --> Menus[Native submenus]
  Menus --> Viewer[Focused viewer action]
```

# Goals
- Show a bounded, deterministic submenu per repository with meaningful Logics work.
- Keep focused viewer actions bound to the repository that produced them.
- Preserve the compact card summary and global Logics actions.

# Non-goals
- No document tree, arbitrary repository browsing, unbounded task list, or direct document editing from the tray.
- No change to Logics manager status selection, viewer server ownership, or session alert grouping.

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
- Product back-reference: `item_115_publish_bounded_logics_repository_groups_in_the_tray_card`
- Task back-reference: `task_069_orchestrate_repository_grouped_logics_tray_navigation`
