## prod_059_cdx_tray_the_tray_companion_released_on_its_own - cdx-tray, the tray companion released on its own
> Date: 2026-11-14
> Status: Proposed
> Related request: `req_085_move_the_tray_companion_into_its_own_cdx_tray_repository`
> Related backlog: `item_172_version_the_tray_contract_and_pin_its_json_shape`, `item_173_create_the_public_cdx_tray_repository_with_its_ci_and_releases`, `item_174_install_the_tray_from_cdx_tray_releases`, `item_175_remove_the_tray_from_cdx_manager_and_announce_contract_changes`
> Related task: `task_089_orchestrate_the_cdx_tray_split`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.
> Indicators reviewed: 2026-11-14 15:01:08

# Overview
The menu-bar/tray companion becomes its own small public project with a versioned JSON contract to cdx, so each side releases at its own pace.

# Goals
- Faster cdx releases: no tray rebuild and no publish wait.
- A tray that only rebuilds when it changes or when the contract does.
- A safe install path that never pairs an incompatible tray and cdx.

# Non-goals
- New tray features.
- Changing the checksum verification model.

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
- Product back-reference: `req_085_move_the_tray_companion_into_its_own_cdx_tray_repository`
- Task back-reference: `task_089_orchestrate_the_cdx_tray_split`
