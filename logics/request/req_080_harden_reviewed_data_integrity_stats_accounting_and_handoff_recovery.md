## req_080_harden_reviewed_data_integrity_stats_accounting_and_handoff_recovery - Harden reviewed data integrity, stats accounting and handoff recovery
> From version: 0.20.14
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Complexity: High
> Theme: Review hardening
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-10-04 17:09:27

# AI Context
- Summary: Consolidates seven reproduced defects and secondary coverage gaps from three audits into nine ordered implementation slices; preserves intentional reporting and handoff limits.
- Keywords: harden, reviewed, data, integrity, stats, accounting, handoff, recovery
- Use when: Delivering profile/memory integrity, stats attribution or exact-source handoff corrections from the October review.
- Skip when: Adding worktree management, new providers, billing reconstruction or live telemetry.

# Needs
- Deliver all seven reproduced defects captured in req_077, req_078 and req_079, with traceable regressions.
- Address secondary model attribution, history-window and duplicate-finalization gaps; make intentional reporting and handoff limits explicit rather than silently changing semantics.

# Context
- User authorized a complete ready-to-dev corpus and commit on 2026-10-04, not implementation. The worktree/workspace feature discussion is explicitly deferred.
- Reviewed baseline 47d36cc / 0.20.14. Initial full suite: 1058 Python tests, 104 Rust tests; focused stats 181 and handoff 76 passed despite synthetic defect reproductions. These are baseline results, not proof of fixes.
- Consolidate the three review requests into this delivery chain while preserving their evidence. Existing completed hardening remains historical; new regressions cover remaining boundaries.
- ADR 030 framing: these changes affect product truth, data ownership and multi-layer recovery, so one product brief and linked slices are appropriate; no separate architectural abstraction is proposed.

# Acceptance criteria
- AC1: A failed initial credential read during force import preserves the original live profile, record, state and credentials; incomplete recovery is explicitly located without exposing secrets.
- AC2: Independent CLI processes appending to the same memory scope retain every accepted note; lock failure is bounded and never reports a successful lost write.
- AC3: All usage-bearing failover attempts retain their own session attribution, measured usage and duration while the registry keeps one logical run; reporting does not double count attempts.
- AC4: Interactive usage excludes transcript growth before launch, preserves attribution confidence for unknown or overlapping boundaries, and does not depend on a 50-entry history window.
- AC5: Custom prices accept only finite nonnegative rates, reject invalid configuration actionably, and handle a zero-input price without division errors or invented relative weights.
- AC6: Headless history preserves provider-reported model identity or supported per-model usage, prices supported evidence, and leaves unknown attribution explicitly unpriced rather than assuming the requested model was served.
- AC7: Stats has one row-finalization path and makes period overlap, partial price coverage, model-relative weighting, current-table repricing and mixed-model estimates explicit in documented text/JSON contracts.
- AC8: Duplicate source identities never silently select an arbitrary native transcript; interactive and non-interactive selection can bind one exact validated native file.
- AC9: Native discovery and explicit terminal fallback work with literal glob metacharacters in supported profile paths without admitting unrelated files or subagents.
- AC10: Handoff retains full source evidence, private unique entries, source-byte checks, instruction-first recovery, and clear disclosure that source availability and agent comprehension are not guaranteed.
- AC11: Synthetic regressions cover all seven reproduced defects and the secondary headless, history-window and contract gaps; appropriate Python, Rust, lint and workflow validations pass without live provider calls.
- AC12: Each original review finding and secondary observation has a named implementation slice or an explicit preserved limitation with validation, and the source reviews remain available as evidence.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_056_trustworthy_local_recovery_and_usage_attribution`
- Architecture decision(s): (none yet)

# References
- logics/request/req_077_review_findings_cross_process_memory_writes_and_early_import_recovery.md
- logics/request/req_078_review_findings_stats_attribution_and_pricing_input_validation.md
- logics/request/req_079_review_findings_handoff_source_ambiguity_and_literal_profile_paths.md
- src/session_backup.py
- src/context_store.py
- src/session_store.py
- src/commands/runs.py
- src/commands/launch.py
- src/commands/status.py
- src/run_usage.py
- src/interactive_usage.py
- src/handoff.py
- src/provider_runtime.py
- src/provider_background.py
- README.md

# Backlog
- `item_156_preserve_live_profiles_on_early_force_import_credential_failures`
- `item_157_serialize_memory_appends_across_independent_cli_processes`
- `item_158_account_for_every_headless_failover_attempt_under_its_actual_session`
- `item_159_measure_interactive_usage_at_real_launch_boundaries_without_a_history_cap`
- `item_160_validate_custom_token_rates_and_support_undefined_relative_weights`
- `item_161_persist_observed_model_attribution_for_headless_usage_pricing`
- `item_162_clarify_stats_period_and_cost_contracts_and_remove_duplicate_finalization`
- `item_163_bind_handoff_selection_to_one_exact_native_source_file`
- `item_164_treat_profile_paths_literally_in_native_and_terminal_transcript_discovery`

# Review coverage map
| Evidence | Disposition | Delivery slice |
| --- | --- | --- |
| req_077 finding 1: displaced live profile | Correct failure boundary and recovery | item_156 |
| req_077 finding 2: accepted note loss | Cross-process serialization | item_157 |
| req_078 finding 1: failover attribution and missing attempts | Correct attempt accounting | item_158 |
| req_078 finding 2: interval contamination | Starting snapshot and explicit uncertainty | item_159 |
| req_078 secondary: 50-entry baseline cap | Remove arbitrary lookup limit | item_159 |
| req_078 finding 3: custom rate failures | Validate rates and undefined weights | item_160 |
| req_078 secondary: headless missing model | Persist observed attribution | item_161 |
| req_078 secondary: duplicate finalization | Remove redundant loop | item_162 |
| req_078 limits: overlapping periods, partial pricing, relative ranking, mixed models, current-table repricing and completed-only reporting | Preserve policy, expose interpretation and prove it with fixtures | item_162 |
| req_079 finding 1: wrong explicit selection | Bind exact eligible native path | item_163 |
| req_079 finding 2: glob metacharacters | Literal native and terminal discovery | item_164 |
| req_079 limits: source dependency and no comprehension guarantee | Preserve source-integrity checks and explicit recovery contract | item_163 |
| Worktree/session-to-branch feature discussion | Deferred by operator; excluded | None |

# Priority
- High: protect live profiles and accepted notes first; execute the remaining Medium-priority accounting and handoff slices afterward according to dependencies.
