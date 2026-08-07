## req_021_close_the_programmatic_cli_contract_gaps_that_force_agent_callers_to_reimplement_cdx_internals - Close the programmatic CLI contract gaps that force agent callers to reimplement cdx internals
> From version: 0.12.4
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: High
> Theme: Agent integration surface
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-07

# Needs
- `cdx` exposes `--json` on every subcommand but its execution model is still synchronous-human-shaped: a run blocks until completion, the assigned `run_id` is never emitted before the run finishes, live output is not readable through the CLI, and argument errors collapse into a single `invalid_request` code carrying a human usage string.
- Programmatic callers therefore reimplement cdx internals to compensate. An audit of the downstream MCP server that wraps this CLI (a sibling private repository, `mcp-server/cdx_mcp_server.py`) found roughly 250 of its 640 lines exist purely as workarounds for these gaps, with no domain logic of their own.
- The workarounds are fragile, not merely verbose: the caller polls `cdx runs` every 300ms for up to 8s to guess which run it just launched by matching `session + cwd + status == running + not-previously-seen`, and gives up with a null `run_id` when session authentication is slow.
- The opaque error contract has already caused a silent false positive in production use: a caller passed a session name together with `--provider` (rejected as mutually exclusive by `_parse_run_args`), received a payload with every field null and code `invalid_request`, and reported the launch as successful because nothing in the response identified the offending arguments.
- Enum values (`permission`, `power`, `kind`) are hand-copied into every downstream caller because cdx publishes no machine-readable schema. This duplication is the root cause of GitHub issue #8, where an `--experimental-yolo` flag was mapped for the ollama provider and never exercised because no caller shared cdx's own definition of the valid permission set.
- cdx is not consumed by one caller: an MCP server, a fleet watchdog cron job, and several agent skills all drive the same CLI, so every gap is paid for repeatedly and independently.

# Context
- `handle_run()` in `src/cli_commands.py:995` resolves `run_id = artifacts['run_id']` at line 1058 and calls `registry.start(...)` immediately after, before `_run_headless_provider_command()` executes the provider. The identifier is therefore known and registered before any long-running work begins, but is only written to stdout in the terminal payload after the provider process exits.
- `handle_run()` has no detached mode. Callers that need a non-blocking launch spawn `cdx run` themselves with `subprocess.Popen(..., start_new_session=True)` and redirect output to a log file they manage. Over SSH this is not implemented at all downstream, because detaching the remote process from the SSH session was never solved — so background launches are unavailable in remote mode.
- `handle_run_status()` at `src/cli_commands.py:968` already returns `artifacts.stdout_path`, and `handle_run_report()` returns the same map, but no subcommand reads that file. Callers fetch the path via `run-status --json`, then open the file directly in local mode or shell out to `tail -n` over SSH — two code paths reimplementing a read of a file cdx itself wrote.
- `run_cdx_error_code()` in `src/run_command.py:17` derives the error code by string-prefix sniffing the exception message: any message starting with `Usage:` or `cdx run:` becomes `invalid_request`. `RUN_USAGE` (`src/cli_args.py:37`) is the entire human usage line, and `_parse_run_args` raises it for every distinct argument mistake, so the mutually-exclusive-arguments case is indistinguishable from a missing `--cwd`.
- `read_run_prompt()` in `src/run_command.py:7` accepts `--prompt TEXT` or reads `--prompt-file PATH` with `open()`. There is no stdin form, so callers handling arbitrary untrusted prompt text (which must never reach a command line) stage a temporary file, transfer it, invoke cdx, then delete it in a `finally` block.
- `handle_runs()` at `src/cli_commands.py:959` accepts only `--limit`, while `cdx history` already supports `--since`, `--from`, and `--to`. A watchdog polling for newly-completed runs must therefore request a fixed window and maintain its own de-duplication set of already-reported run ids, capped at a fixed size so its state file does not grow without bound.
- The missing cursor is a correctness gap, not only a verbosity one: the downstream watchdog polls a fixed 20-run window every 15 minutes, so if more than 20 runs complete inside one interval the older ones scroll out of the window and are never reported at all. A caller-side de-duplication set can only suppress repeats; it cannot recover a completion it never observed.
- `run_result_payload()` in `src/run_command.py:107` hardcodes `"warnings": []` and never populates it, while `handle_status()` composes a real warnings list for its own payload (`src/cli_commands.py:2338` onward). The run contract therefore declares a warning channel it never uses, and a known silent degradation — a Codex-backed run below `full` permission losing provider network access while still exiting zero — reaches callers only as prose in downstream documentation.
- GitHub issue #8, closed on 2026-08-07, removed a permission flag that never existed in the ollama CLI. It survived undetected precisely because the downstream permission enum was a hand-maintained copy rather than a value obtained from cdx.

# Acceptance criteria
- AC1: `cdx run --detach --json` registers the run, launches the provider process detached from the invoking process, and returns immediately with a payload containing the assigned `run_id`, without waiting for the provider to finish; the detached process survives the parent exiting, including when cdx was itself invoked over a non-interactive SSH session.
- AC2: The `run_id` assigned to a run is observable at launch time in both detached and non-detached modes, so a caller never has to poll `cdx runs` to discover the identity of the run it just started.
- AC3: `cdx run-tail <run_id> [--lines N] --json` returns the last N lines of that run's recorded `stdout_path` together with the run's current status, works whether the run is in progress or already finished, and returns a specific error code when no `stdout_path` was recorded for the run.
- AC4: Argument and usage failures return a specific machine-readable `error.code` naming the failure class rather than the single catch-all `invalid_request`, and the payload identifies the offending argument names; the mutually-exclusive session-and-provider case is distinguishable from a missing required argument by code alone, without parsing any human-readable message.
- AC5: `cdx schema --json` emits the machine-readable contract for programmatic callers: the valid values for `permission`, `power`/`reasoning-effort`, and `kind`, plus the declared mutually-exclusive argument groups, so a caller can validate input against cdx's own definitions instead of a hand-copied duplicate.
- AC6: `cdx run --prompt-file -` reads the prompt from standard input, allowing a caller to pipe arbitrary untrusted prompt text without staging a temporary file and without ever placing the text on a command line.
- AC7: `cdx runs --since <cursor> --json` returns every run that completed after the given cursor, bounded by the cursor rather than by a fixed row count, so a polling caller detects newly-completed runs without maintaining its own set of already-seen run ids and without losing completions that fall outside a fixed window. The accepted cursor forms are consistent with those `cdx history --since` already accepts.
- AC8: All existing behavior is preserved: a `cdx run` without `--detach` still blocks and returns the same completion payload, `run-status`/`run-report`/`runs` keep their current shapes, and the `schema_version` contract is respected for every added or changed field.
- AC9: The README documents the programmatic surface as an explicit contract for non-interactive callers: detached launch, run identity at launch, live tail, error codes, schema discovery, stdin prompts, the runs cursor, and the run warning channel.
- AC10: The run payload's `warnings` list is populated rather than hardcoded empty, and a run launched at a permission level known to disable provider network access carries a warning naming the provider, the effective permission, and the consequence — on the successful path as well as the failing one, since the run exits zero either way.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_011_programmatic_cli_contract_for_non_interactive_callers`
- Architecture decision(s): (none yet)

# References
- src/cli_commands.py
- src/cli_args.py
- src/run_command.py
- src/run_registry.py
- src/provider_runtime.py
- README.md
- test/test_cli_py.py
- test/test_run_registry_py.py
- test/test_provider_runtime_helpers_py.py

# AI Context
- Summary: Close the programmatic CLI contract gaps that force agent callers to reimplement cdx internals
- Keywords: request-chain-scaffold, close the programmatic cli contract gaps that force agent callers to reimplement cdx internals, development-ready
- Use when: You need to implement or review the scaffolded workflow for Close the programmatic CLI contract gaps that force agent callers to reimplement cdx internals.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_041_add_detached_run_launch_returning_run_identity_immediately`
- `item_042_add_run_tail_subcommand_for_live_run_output`
- `item_043_replace_catch_all_usage_errors_with_specific_machine_readable_error_codes`
- `item_044_publish_machine_readable_schema_for_enums_and_argument_constraints`
- `item_045_accept_prompt_on_standard_input_and_add_a_completion_cursor_to_runs`
- `item_046_populate_run_payload_warnings_for_known_silent_degradations`
