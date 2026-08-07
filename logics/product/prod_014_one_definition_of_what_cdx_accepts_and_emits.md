## prod_014_one_definition_of_what_cdx_accepts_and_emits - One definition of what cdx accepts and emits
> Date: 2026-08-07
> Status: Proposed
> Related request: `req_024_give_cdx_one_source_of_truth_for_the_values_it_accepts_and_the_provider_flags_it_emits`
> Related backlog: `item_051_collapse_the_duplicated_accepted_value_enums_into_single_definitions`, `item_052_accept_the_permission_aliases_in_cdx_set_as_well_as_cdx_run`, `item_053_add_an_opt_in_check_that_mapped_provider_flags_exist_in_the_provider_cli`
> Related task: `task_035_orchestrate_one_source_of_truth_for_accepted_values_and_provider_flags`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.

# Overview
Collapse the duplicated accepted-value enums into single definitions every command and the published schema derive from, make `cdx set` and `cdx run` agree on the values they take, and add an opt-in check that the provider flags cdx emits actually exist in the provider CLIs.

# Goals
- Make it impossible for two commands in cdx to disagree about a valid value.
- Make `cdx schema --json` describe the CLI rather than one command of it.
- Catch a mapped provider flag that the provider does not have, before a user does.
- Leave one place to edit when an accepted value or a provider mapping changes.

# Non-goals
- No new accepted values, and no removal of ones that work today.
- No change to how permissions map to provider flags, only verification that the mapping is real.
- No provider CLI probing in the default `cdx doctor` path.
- No runtime verification before each run; this is a diagnostic, not a launch-time gate.
- No unification of the session selection rankings, which is tracked under `req_022`.

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
- Product back-reference: `req_024_give_cdx_one_source_of_truth_for_the_values_it_accepts_and_the_provider_flags_it_emits`
- Task back-reference: `task_035_orchestrate_one_source_of_truth_for_accepted_values_and_provider_flags`
