## task_039_orchestrate_executable_quota_routing_across_accounts_and_providers - Orchestrate executable quota routing across accounts and providers
> From version: 0.14.0
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 85%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Establish the baseline: capture today's `cdx run --json` payload for a success and a failure, today's `cdx resume`/`cdx can-resume` behaviour, and today's `cdx configs` output, so every later change is checked against what users and callers observe now.
- [ ] 2. Wave 1 - the two pinnable settings, because they are the established pattern with the lowest risk and they exercise every touch point (`session_service`, `cli_args`, `cli_helpers`, `commands/status`, `provider_runtime`) that later waves reuse. Mirror `rtk` as the reference implementation.
- [ ] 3. Wave 2 - session identity, before failover and not after. Failover needs a reliable anchor for continuation; building it on transcript scraping first and migrating later would mean writing the hardest part twice. Keep the recency path as the fallback throughout.
- [ ] 4. Wave 3 - rate-limit detection alone, isolated behind one function per provider and tested against recorded provider output before anything depends on it. This is the genuinely new part of the request and the part most likely to be wrong; treat a mis-detection as worse than no detection, since a false positive would migrate a healthy run off a working account.
- [ ] 5. Wave 4 - the failover loop itself, composing the detection from wave 3, `rank_sessions`, and the context transfer from wave 2. Extend the run record to a sequence of occupancies first, so no run is ever recorded in a shape the reporting cannot express.
- [ ] 6. Wave 5 - the passthrough escape hatch, deliberately after the mapped settings so the boundary between validated and unvalidated arguments is drawn once, with the schema and doctor exclusions written in the same change that introduces the feature rather than added afterwards.
- [ ] 7. Wave 6 - background delegation, last because it changes an execution path that already works and carries the least user-visible upside. Capability detection first, delegation second, with the in-house path untouched as the fallback.
- [ ] 8. Throughout: the ollama provider is not touched in any wave. Re-read the request non-goals before any change to provider dispatch.
- [ ] 9. Closeout: verify each request AC against observed command output rather than by inspection, and record which provider CLI versions the detection in wave 3 was verified against, since that is the part most likely to drift.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_063_add_budget_and_fallback_model_as_pinnable_launch_settings`
- `item_064_anchor_resume_and_handoff_on_a_provider_native_session_identity`
- `item_065_continue_a_headless_run_on_the_next_eligible_account_after_a_rate_limit`
- `item_066_pass_unvalidated_provider_arguments_through_instead_of_mapping_every_flag`
- `item_067_delegate_background_execution_to_the_provider_where_the_installed_cli_supports_it`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1, request-AC2, request-AC3, request-AC13 -> `item_063_add_budget_and_fallback_model_as_pinnable_launch_settings`. Proof deferred to slice closeout.
- request-AC4, request-AC5, request-AC13 -> `item_064_anchor_resume_and_handoff_on_a_provider_native_session_identity`. Proof deferred to slice closeout.
- request-AC6, request-AC7, request-AC8, request-AC13 -> `item_065_continue_a_headless_run_on_the_next_eligible_account_after_a_rate_limit`. Proof deferred to slice closeout.
- request-AC9, request-AC10, request-AC13 -> `item_066_pass_unvalidated_provider_arguments_through_instead_of_mapping_every_flag`. Proof deferred to slice closeout.
- request-AC11, request-AC12, request-AC13 -> `item_067_delegate_background_execution_to_the_provider_where_the_installed_cli_supports_it`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# AI Context
- Summary: Orchestrate executable quota routing across accounts and providers
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_028_turn_quota_awareness_from_advice_into_execution_across_accounts_and_providers`
- Product brief(s): `prod_018_executable_quota_routing`
- Architecture decision(s): (none yet)
