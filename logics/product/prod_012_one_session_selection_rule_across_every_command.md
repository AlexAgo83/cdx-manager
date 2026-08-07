## prod_012_one_session_selection_rule_across_every_command - One session selection rule across every command
> Date: 2026-08-07
> Status: Proposed
> Related request: `req_022_unify_the_two_divergent_session_selection_rankings_into_one_contract`
> Related backlog: `item_047_extract_one_parameterized_session_ranking_used_by_every_selector`, `item_048_make_the_priority_setting_count_in_next_status_and_ready`
> Related task: `task_033_orchestrate_the_unified_session_selection_ranking`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.

# Overview
Replace the two divergent session ranking algorithms with a single parameterized rule, so every command that picks a session picks the same one, and so a user's `--priority` setting means the same thing everywhere.

# Goals
- Give cdx one definition of 'the best session to use right now'.
- Make the `--priority` setting effective in every command that selects or recommends a session.
- Keep the strengths of both current implementations rather than picking one and losing the other.
- Make the ranking explainable: a caller should be able to learn why a session won.
- Leave one place to change when a future selection rule is added.

# Non-goals
- No new selection inputs such as cost, latency, or historical success rate.
- No change to how status rows themselves are gathered or refreshed.
- No cross-provider selection in `cdx run --provider`, which is provider-scoped by definition.
- No change to the `cdx ready` to `cdx notify --next-ready` aliasing.
- No retuning of which session wins in cases where both current rankings already agree.

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
- Product back-reference: `req_022_unify_the_two_divergent_session_selection_rankings_into_one_contract`
- Task back-reference: `task_033_orchestrate_the_unified_session_selection_ranking`
