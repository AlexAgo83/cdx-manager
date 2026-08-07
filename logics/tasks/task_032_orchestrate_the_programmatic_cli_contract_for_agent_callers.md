## task_032_orchestrate_the_programmatic_cli_contract_for_agent_callers - Orchestrate the programmatic CLI contract for agent callers
> From version: 0.12.4
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Establish the baseline: capture the current payloads for a blocking `cdx run`, a usage failure, `runs`, and `run-status`, so every later change can be checked against what callers observe today.
- [ ] 2. Wave 1 - error contract and schema first, because the later waves add arguments whose failures should already be reported with specific codes: introduce the structured argument error in `src/cli_args.py`, retire message-prefix sniffing in `run_cdx_error_code()` for the classified cases, then add `cdx schema --json` deriving its values from the parser's own definitions plus the agreement test that prevents drift.
- [ ] 3. Wave 2 - detached launch: add `--detach` to the run parser, branch in `handle_run()` after `registry.start()`, and make the detached child survive both a local parent exit and a non-interactive SSH session. Verify the detached process itself transitions the registry entry to a terminal status, since the launching process is gone. Confirm the blocking path's payload is byte-for-byte unchanged.
- [ ] 4. Wave 3 - run-tail: add the subcommand next to `run-status`/`run-report`, reading the registry's recorded `stdout_path`. Exercise it against a real in-progress detached run from wave 2, not only a fixture, to confirm partial lines and undecodable bytes are handled.
- [ ] 5. Wave 4 - stdin prompt and runs cursor: extend `read_run_prompt()` for `-`, reuse the existing `--since` parsing from `cdx history` for `cdx runs`, and confirm both compose with `--detach`.
- [ ] 6. Update the README with a dedicated programmatic-caller section covering detached launch, run identity at launch, live tail, error codes, schema discovery, stdin prompts, and the runs cursor.
- [ ] 7. Verify the end-to-end shape the downstream callers actually need, without modifying them: launch detached, read `run_id` from the launch payload, tail it while running, and poll `runs --since` until it reports completion.
- [ ] 8. Run the focused CLI, run-registry, and provider-runtime test files, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_041_add_detached_run_launch_returning_run_identity_immediately`
- `item_042_add_run_tail_subcommand_for_live_run_output`
- `item_043_replace_catch_all_usage_errors_with_specific_machine_readable_error_codes`
- `item_044_publish_machine_readable_schema_for_enums_and_argument_constraints`
- `item_045_accept_prompt_on_standard_input_and_add_a_completion_cursor_to_runs`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1, request-AC2, request-AC8 -> `item_041_add_detached_run_launch_returning_run_identity_immediately`. Proof deferred to slice closeout.
- request-AC3, request-AC8 -> `item_042_add_run_tail_subcommand_for_live_run_output`. Proof deferred to slice closeout.
- request-AC4, request-AC8 -> `item_043_replace_catch_all_usage_errors_with_specific_machine_readable_error_codes`. Proof deferred to slice closeout.
- request-AC5, request-AC9 -> `item_044_publish_machine_readable_schema_for_enums_and_argument_constraints`. Proof deferred to slice closeout.
- request-AC6, request-AC7, request-AC8, request-AC9 -> `item_045_accept_prompt_on_standard_input_and_add_a_completion_cursor_to_runs`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# AI Context
- Summary: Orchestrate the programmatic CLI contract for agent callers
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_021_close_the_programmatic_cli_contract_gaps_that_force_agent_callers_to_reimplement_cdx_internals`
- Product brief(s): `prod_011_programmatic_cli_contract_for_non_interactive_callers`
- Architecture decision(s): (none yet)
