## task_039_orchestrate_executable_quota_routing_across_accounts_and_providers - Orchestrate executable quota routing across accounts and providers
> From version: 0.14.0
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-08

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Establish the baseline: capture today's `cdx run --json` payload for a success and a failure, today's `cdx resume`/`cdx can-resume` behaviour, and today's `cdx configs` output, so every later change is checked against what users and callers observe now.
- [x] 2. Wave 1 - the two pinnable settings, because they are the established pattern with the lowest risk and they exercise every touch point (`session_service`, `cli_args`, `cli_helpers`, `commands/status`, `provider_runtime`) that later waves reuse. Mirror `rtk` as the reference implementation.
- [x] 3. Wave 2 - session identity, before failover and not after. Failover needs a reliable anchor for continuation; building it on transcript scraping first and migrating later would mean writing the hardest part twice. Keep the recency path as the fallback throughout.
- [x] 4. Wave 3 - rate-limit detection alone, isolated behind one function per provider and tested against recorded provider output before anything depends on it. This is the genuinely new part of the request and the part most likely to be wrong; treat a mis-detection as worse than no detection, since a false positive would migrate a healthy run off a working account.
- [x] 5. Wave 4 - the failover loop itself, composing the detection from wave 3, `rank_sessions`, and the context transfer from wave 2. Extend the run record to a sequence of occupancies first, so no run is ever recorded in a shape the reporting cannot express.
- [x] 6. Wave 5 - the passthrough escape hatch, deliberately after the mapped settings so the boundary between validated and unvalidated arguments is drawn once, with the schema and doctor exclusions written in the same change that introduces the feature rather than added afterwards.
- [x] 7. Wave 6 - background delegation, last because it changes an execution path that already works and carries the least user-visible upside. Capability detection first, delegation second, with the in-house path untouched as the fallback.
- [x] 8. Throughout: the ollama provider is not touched in any wave. Re-read the request non-goals before any change to provider dispatch.
- [x] 9. Closeout: verify each request AC against observed command output rather than by inspection, and record which provider CLI versions the detection in wave 3 was verified against, since that is the part most likely to drift.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_063_add_budget_and_fallback_model_as_pinnable_launch_settings`
- `item_064_anchor_resume_and_handoff_on_a_provider_native_session_identity`
- `item_065_continue_a_headless_run_on_the_next_eligible_account_after_a_rate_limit`
- `item_066_pass_unvalidated_provider_arguments_through_instead_of_mapping_every_flag`
- `item_067_delegate_background_execution_to_the_provider_where_the_installed_cli_supports_it`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: **tested.** `test_set_persists_budget_and_fallback_model_and_unset_clears_them` stores and clears the ceiling; `test_set_rejects_budgets_that_express_nothing` rejects 0, -1, abc, 20000 and nan with nothing written to the store.
- request-AC2 -> This task. Proof: **tested.** `test_set_validates_every_element_of_the_fallback_model_list` rejects an empty, over-long or control-character element of the comma-separated list; the list form itself was the correction that reading the CLI produced.
- request-AC3 -> This task. Proof: **observed.** A real headless run on the `digital` Claude account carrying `--budget 1 --fallback-model haiku` returned ok, exit 0, 24 129 tokens, so the provider accepts both on the `--print` path. `test_interactive_and_resume_claude_specs_reject_the_print_only_flags` and `test_codex_specs_never_carry_the_claude_only_settings` hold the other half.
- request-AC4 -> This task. Proof: **observed, both provenances.** Codex: `cdx run main` wrote `rollout-2026-08-08T22-11-25-019fe300-7531-7781-9296-708de11ff3da.jsonl` and cdx read `019fe300-...` back, matching the filename. Claude: cdx minted `6e8e9e0b-39db-4ade-a9fb-bc895d5ced9f`, the CLI accepted it as `--session-id` (exit 0), and `--resume 6e8e9e0b-...` recalled the previous turn's answer, so the identifier resumed that conversation and not another.
- request-AC5 -> This task. Proof: **observed.** `cdx can-resume main --json` reported `provider_last` / `no_recorded_conversation` before the run and `provider_conversation_id` / `observed` after it; `digital` reports `imposed`.
- request-AC6 -> This task. Proof: **observed.** `cdx run work6 --failover` on a genuinely exhausted account migrated to `work1` and succeeded. The first attempt did not migrate, which is how the matcher defect was found: codex-cli emits `{"type":"error","message":"Your workspace is out of credits."}`, a wording the first matcher could not match. Corroboration by refreshed status is what makes an unseen wording still migrate.
- request-AC7 -> This task. Proof: **observed.** That migration is recorded as one run, `34818a1a062a4ca8abd79b56f634d5f1`, whose occupancies read `work6 -> provider_reported_exhaustion` then `work1 -> succeeded`, and `cdx runs` lists it once.
- request-AC8 -> This task. Proof: **tested.** `test_failover_reports_exhausting_every_account_distinctly` asserts `failover_exhausted` when no eligible session remains, distinct from `provider_failed`; the transition bound reports `failover_limit_reached`.
- request-AC9 -> This task. Proof: **tested.** `test_extra_args_reach_every_spec_unchanged_and_never_via_a_shell` shows quoted values surviving as literal argv entries in all three specs; `test_extra_args_land_after_the_settings_cdx_maps` shows the override ordering. Never exercised against a real provider.
- request-AC10 -> This task. Proof: **tested.** `cdx schema --json` publishes an `unvalidated` section naming extra_args, why, and what does not check it; `doctor --check-provider-flags` ignores it.
- request-AC11 -> This task. Proof: **observed, and it failed.** A live `cdx run digital --detach` against Claude Code 2.1.226 showed delegation cannot be done safely as designed: the provider ignores `--session-id` under `--bg` (cdx asked for `6e8e9e0b-...`, got `373c3949-...`), the reported `pid` belonged to a `claude bg-spare` daemon helper and went `null` within a minute, and `status` can be absent entirely alongside an undocumented `state: "blocked"`. cdx therefore failed to identify the agent it had started, fell back to the in-house launcher, and the same task ran twice - once untracked. Delegation is now off unless `CDX_EXPERIMENTAL_NATIVE_BG=1`, and the silent fallback is replaced by a loud failure so a duplicate run cannot happen. The AC is not met; it is disabled rather than shipped broken.
- request-AC12 -> This task. Proof: **tested.** The in-house path is unchanged and its tests still pass; `test_background_argv_never_carries_print_only_flags` locks the regression that `--bg` must not receive print-only flags. The record names which path carried a run.
- request-AC13 -> This task. Proof: **observed by diff.** `git diff v0.14.0..HEAD -- src/` touches no ollama dispatch, the `PROVIDER_OLLAMA` permission mapping is unchanged, and `test_providers_without_a_matcher_are_never_classified` asserts ollama is never classified for failover.
Proofs are marked by how they were obtained. `observed` means a real provider
CLI produced the result on a live account; `tested` means the behaviour is
covered by the suite but never met a real provider; `unverified` means neither.
Nothing here is proven by inspection alone.


Cross-platform: the suite was run on the maintainer's Windows machine as well as
macOS. 614 passed, 5 skipped. The single failure,
`test_concurrent_starts_do_not_lose_records`, reproduces identically on the
`v0.14.0` tag on the same machine, so it predates this request: `msvcrt.locking`
gives up under 20 concurrent writers. Recorded as a finding, not fixed here.

# Validation
- (no validation recorded yet)
- 620 tests on macOS; 614 passed + 5 skipped on the maintainer's Windows machine. Failover, session identity, budget and fallback verified against live Codex and Claude accounts.
- Finish workflow executed on 2026-08-08.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-08.
- Linked backlog item(s): `item_063_add_budget_and_fallback_model_as_pinnable_launch_settings`, `item_064_anchor_resume_and_handoff_on_a_provider_native_session_identity`, `item_065_continue_a_headless_run_on_the_next_eligible_account_after_a_rate_limit`, `item_066_pass_unvalidated_provider_arguments_through_instead_of_mapping_every_flag`, `item_067_delegate_background_execution_to_the_provider_where_the_installed_cli_supports_it`
- Related request(s): `req_028_turn_quota_awareness_from_advice_into_execution_across_accounts_and_providers`

# AI Context
- Summary: Orchestrate executable quota routing across accounts and providers
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_028_turn_quota_awareness_from_advice_into_execution_across_accounts_and_providers`
- Product brief(s): `prod_018_executable_quota_routing`
- Architecture decision(s): (none yet)
