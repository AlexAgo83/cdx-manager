## task_032_orchestrate_the_programmatic_cli_contract_for_agent_callers - Orchestrate the programmatic CLI contract for agent callers
> From version: 0.12.4
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 100%
> Progress: 90%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Indicators reviewed: 2026-08-07

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [x] 1. Establish the baseline: capture the current payloads for a blocking `cdx run`, a usage failure, `runs`, and `run-status`, so every later change can be checked against what callers observe today.
- [x] 2. Wave 1 - error contract and schema first, because the later waves add arguments whose failures should already be reported with specific codes: introduce the structured argument error in `src/cli_args.py`, retire message-prefix sniffing in `run_cdx_error_code()` for the classified cases, then add `cdx schema --json` deriving its values from the parser's own definitions plus the agreement test that prevents drift.
- [x] 3. Wave 2 - detached launch: add `--detach` to the run parser, branch in `handle_run()` after `registry.start()`, and make the detached child survive both a local parent exit and a non-interactive SSH session. Verify the detached process itself transitions the registry entry to a terminal status, since the launching process is gone. Confirm the blocking path's payload is byte-for-byte unchanged.
- [x] 4. Wave 3 - run-tail: add the subcommand next to `run-status`/`run-report`, reading the registry's recorded `stdout_path`. Exercise it against a real in-progress detached run from wave 2, not only a fixture, to confirm partial lines and undecodable bytes are handled.
- [x] 5. Wave 4 - stdin prompt and runs cursor: extend `read_run_prompt()` for `-`, reuse the existing `--since` parsing from `cdx history` for `cdx runs`, and confirm both compose with `--detach`.
- [x] 6. Wave 5 - run warnings: replace the hardcoded `"warnings": []` in `run_result_payload()` with a populated list, deriving the network-restricted-permission condition from the provider and effective permission already resolved for the run. Reuse the warning entry shape `handle_status()` already emits, and carry the warning into wave 2's detached launch payload where the condition is known at launch.
- [x] 7. Update the README with a dedicated programmatic-caller section covering detached launch, run identity at launch, live tail, error codes, schema discovery, stdin prompts, the runs cursor, and the run warning channel.
- [x] 8. Verify the end-to-end shape the downstream callers actually need, without modifying them: launch detached, read `run_id` from the launch payload, tail it while running, and poll `runs --since` until it reports completion, checking that a network-restricted permission surfaces its warning on a run that still exits zero.
- [x] 9. Run the focused CLI, run-registry, and provider-runtime test files, then `logics-manager lint --require-status` and `logics-manager audit --group-by-doc` before closeout.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_041_add_detached_run_launch_returning_run_identity_immediately`
- `item_042_add_run_tail_subcommand_for_live_run_output`
- `item_043_replace_catch_all_usage_errors_with_specific_machine_readable_error_codes`
- `item_044_publish_machine_readable_schema_for_enums_and_argument_constraints`
- `item_045_accept_prompt_on_standard_input_and_add_a_completion_cursor_to_runs`
- `item_046_populate_run_payload_warnings_for_known_silent_degradations`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_041`. Proof: `test_run_detach_returns_run_id_without_waiting` and the two detached-child tests. The Windows branch is exercised by CI only since `49c6eaf`; the spawn is stubbed, so the flags are proven, not child survival.
- request-AC2 -> `item_041`. Proof: the run_id is in the launch payload in both modes, so no caller polls `cdx runs` to learn what it just started.
- request-AC3 -> `item_042`. Proof: four `run_tail` tests covering running, not-yet-written, partial-leading-line, and the specific error code when no stdout_path was recorded.
- request-AC4 -> `item_043`. Proof: `test_json_error_payload_has_machine_readable_contract` and `test_empty_power_blames_the_flag_that_was_passed`.
- request-AC5 -> `item_044`. Proof: `cdx_schema()` returns the parser's own objects; four schema tests assert it cannot advertise a value the parser rejects.
- request-AC6 -> `item_045`. Proof: `test_run_reads_prompt_from_stdin` and `test_run_refuses_stdin_prompt_from_a_terminal`.
- request-AC7 -> `item_042`. Proof: `test_runs_since_is_bounded_by_the_cursor_not_by_limit`, **added at closeout**. The behaviour shipped and is documented in the README, but nothing exercised it; the test was mutation-checked by making the handler honour `--limit` alongside the cursor, and it failed as intended.
- request-AC8 -> all slices. Proof: the suite passed unchanged through delivery; `run-status`, `run-report` and `runs` kept their shapes and `schema_version` was respected.
- request-AC9 -> `item_041`, `item_042`, `item_044`. Proof: the README documents detached launch, run identity, live tail, error codes, schema discovery, stdin prompts, the runs cursor and the warning channel.
- request-AC10 -> `item_046`. Proof: three warning tests, including the successful-path case a caller inspecting only failures would miss.

# Validation
- `python3 -m pytest test/` - 527 passed.
- `ruff check src/ test/` - clean.
- End-to-end against a stubbed provider CLI: detached launch returned `run_id` immediately; `run-tail` showed live output after the launcher had exited; the detached child reached `succeeded` with no supervisor; `runs --since` reported the completion and warned that `--limit` was ignored.
- `--permission review` on a Codex run emitted `network_disabled_by_permission` on a payload with `ok: true` and `exit_code: 0`.

# Report
- Delivered across five waves in the planned order; error contract and schema landed first so later waves' new arguments reported specific codes from the start.
- Deviation from `item_041`: `--detach` and `--timeout-seconds` were left compatible rather than mutually exclusive. The timeout is enforced by the detached child, so it stays meaningful without the launcher waiting; no option in the current flag set only makes sense while waiting, so the planned exclusivity check would have been an invented constraint. The schema's mutually-exclusive list reflects this.
- `invalid_reasoning_effort` was kept for unsupported effort values rather than folded into `invalid_argument_value`: it was already specific, and the new codes exist to split what used to be indistinguishable, not to rename what was not.
- `--detach` re-invokes cdx rather than forking, so the child walks the ordinary blocking path and registry bookkeeping, usage extraction, and history run once each in already-tested code. `os.fork()` was rejected for lack of Windows support.
- Two pre-existing test failures were found and fixed: `test_cli_py` and `test_runtime_py` still asserted the `--experimental-yolo` ollama flag removed under GitHub issue #8, so the suite had been red since that fix. The launch behavior itself was already correct.
- `format_json_error` was taught to honor a declared error code; without it, argument errors raised by commands that bubble to the CLI entry point (such as `run-tail`) lost their code on the way out.

# AI Context
- Summary: Orchestrate the programmatic CLI contract for agent callers
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Links
- Request: `req_021_close_the_programmatic_cli_contract_gaps_that_force_agent_callers_to_reimplement_cdx_internals`
- Product brief(s): `prod_011_programmatic_cli_contract_for_non_interactive_callers`
- Architecture decision(s): (none yet)
