## prod_017_a_session_service_whose_file_boundaries_match_its_real_seams - A session service whose file boundaries match its real seams
> Date: 2026-08-07
> Status: Proposed
> Related request: `req_027_split_session_service_along_the_two_seams_the_coupling_measurement_supports`
> Related backlog: `item_060_move_the_shared_helpers_into_a_session_service_utility_layer`, `item_061_extract_the_status_group_into_its_own_module`, `item_062_extract_the_backup_group_and_record_why_the_other_groups_stay`
> Related task: `task_038_orchestrate_the_measured_session_service_file_split`
> Related architecture: (none yet)
> Reminder: Update status, linked refs, scope, decisions, success signals, and open questions when you edit this doc.

# Overview
Cut `session_service.py` only where the coupling measurement says it can be cut, so the resulting files are independently readable rather than merely smaller.

# Goals
- Two new modules that can be read without holding the rest of the service in mind.
- A shared utility layer that both new modules and the original depend on, with no import cycling back.
- A recorded reason for every group that was left in place, so the decision survives the next reader's instinct to finish the job.

# Non-goals
- Splitting the groups the measurement does not support.
- Changing the service interface or any caller.
- Introducing a service class, registry, or dependency-injection layer.
- Rewriting the existing tests to the new shape.

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
- Product back-reference: `req_027_split_session_service_along_the_two_seams_the_coupling_measurement_supports`
- Task back-reference: `task_038_orchestrate_the_measured_session_service_file_split`
