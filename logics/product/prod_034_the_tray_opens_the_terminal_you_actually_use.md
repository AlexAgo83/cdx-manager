## prod_034_the_tray_opens_the_terminal_you_actually_use - The tray opens the terminal you actually use
> Date: 2026-08-11
> Status: Proposed
> Related request: `req_047_let_the_operator_choose_which_terminal_the_tray_opens`
> Related backlog: `item_095_add_a_cdx_owned_terminal_preference_the_tray_honours`
> Related task: `task_058_orchestrate_the_preferred_tray_terminal`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.

# Overview
Let one CDX-owned preference decide which terminal a session row opens, with a safe fallback and no way to smuggle a command through it.

# Goals
- Open the terminal the operator works in, rather than the one the platform happens to ship.
- Keep the preference in CDX, where every other tray setting already lives.
- Fall back rather than fail when the named terminal is not there.

# Non-goals
- Arbitrary launch commands, shell templates, or per-session terminal choices.
- Detecting the terminal the user is currently in, or managing terminal profiles.
- Changing what is run inside the terminal once it opens.

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
- Product back-reference: `req_047_let_the_operator_choose_which_terminal_the_tray_opens`
- Task back-reference: `task_058_orchestrate_the_preferred_tray_terminal`
