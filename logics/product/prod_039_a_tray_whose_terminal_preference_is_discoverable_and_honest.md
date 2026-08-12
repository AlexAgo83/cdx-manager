## prod_039_a_tray_whose_terminal_preference_is_discoverable_and_honest - A tray whose terminal preference is discoverable and honest
> Date: 2026-08-12
> Status: Proposed
> Related request: `req_052_let_the_operator_choose_the_tray_s_target_terminal_on_every_platform`
> Related backlog: `item_101_declare_the_launchable_terminals_in_cdx_and_publish_the_candidates`, `item_102_honour_powershell_pwsh_and_cmd_on_windows_and_prove_the_branches_match_the_catalogue`, `item_103_offer_the_terminal_choice_as_a_tray_submenu`
> Related task: `task_063_deliver_a_discoverable_and_honest_tray_terminal_choice`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.

# Overview
CDX declares which terminals it can launch on this host, the tray lets the operator pick one, and every offered choice is one that will actually open.

# Goals
- Make the terminal preference discoverable where the operator already is: the tray menu.
- Give the CLI a discovery command so a name never has to be guessed.
- Guarantee that an offered choice is an honoured choice, on every platform.
- Keep one definition of what is launchable, so the CLI and the companion cannot drift apart.

# Non-goals
- Letting the preference hold a command line, a path, or arguments.
- Adding an interactive CLI picker; `list` plus the existing `set` covers the discovery need.
- Choosing the shell independently of the terminal on macOS and Linux, where the application brings its own.
- Detecting terminals CDX has no documented way to launch, however popular they are.

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
- Product back-reference: `req_052_let_the_operator_choose_the_tray_s_target_terminal_on_every_platform`
- Task back-reference: `task_063_deliver_a_discoverable_and_honest_tray_terminal_choice`
