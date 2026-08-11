## prod_035_a_logics_card_that_knows_which_repository_it_is_about - A Logics card that knows which repository it is about
> Date: 2026-08-11
> Status: Proposed
> Related request: `req_048_give_the_logics_tray_card_a_repository_to_report_on`
> Related backlog: `item_096_name_the_repository_the_logics_card_reports_on`
> Related task: `task_059_orchestrate_the_repository_aware_logics_card`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.

# Overview
Let the Logics tray card report on a repository the operator named, rather than on whichever directory happened to ask.

# Goals
- Make an enabled card visible in the tray it was built for.
- Keep the answer durable across install, update and restart.
- Keep silence the behaviour when nothing is named or nothing is there.

# Non-goals
- Detecting repositories automatically, or reporting on several at once.
- Changing what the card shows or how often it refreshes.
- Any new Logics capability beyond the status the adapter already reads.

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
- Product back-reference: `req_048_give_the_logics_tray_card_a_repository_to_report_on`
- Task back-reference: `task_059_orchestrate_the_repository_aware_logics_card`
