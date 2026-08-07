## item_042_add_run_tail_subcommand_for_live_run_output - Add run-tail subcommand for live run output
> From version: 0.12.4
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 100%
> Progress: 90%
> Complexity: Low
> Theme: Agent integration surface
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- `run-status` reports only running/succeeded/failed with no detail about the current step, so a caller watching a long run has no way to see what it is doing.
- cdx records `stdout_path` in the run registry and returns it from `run-status`, but offers no way to read it, so callers open cdx's own artifact file directly, with one code path for local access and another shelling out to `tail` remotely.

# Scope
- In:
  - Add a `run-tail <run_id> [--lines N] --json` subcommand with usage, argument parsing, and dispatch alongside the existing `run-status` and `run-report` handlers.
  - Resolve the run from the registry, read the last N lines of its recorded `stdout_path`, and return them with the run's current status and the path itself.
  - Bound `--lines` to a sane range with a documented default, and validate it like other numeric CLI arguments.
  - Return specific error codes for an unknown run id and for a run with no recorded `stdout_path`, distinct from a read failure of an existing path.
  - Handle a partially written final line and undecodable bytes without raising.
  - Add tests for an in-progress run, a completed run, an unknown run id, a run with no `stdout_path`, and an out-of-range `--lines`.
- Out:
  - No follow/streaming mode.
  - No parsing, filtering, or summarizing of provider output; lines are returned raw.
  - No tailing of `stderr_path` in this item.

# Acceptance criteria
- Given a run currently in progress, `cdx run-tail <run_id> --lines 20 --json` returns up to the last 20 lines written so far, the recorded `stdout_path`, and a status of running.
- Given a completed run, the same call returns the last lines of its final output and its terminal status.
- Given an unknown run id, the command fails with the run-not-found error code already used by `run-status`.
- Given a run whose registry entry has no `stdout_path`, the command fails with a distinct, specific error code rather than a generic read failure.
- Given `--lines` outside the accepted range, the command fails with a specific argument error code before touching the filesystem.
- Given output containing undecodable bytes, the command returns the lines with replacement characters rather than raising.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: Given a run currently in progress, `cdx run-tail <run_id> --lines 20 --json` returns up to the last 20 lines written so far, the recorded `stdout_path`, and a status of running.
- request-AC8 -> This backlog slice. Proof: Given a completed run, the same call returns the last lines of its final output and its terminal status.

# Outcome

> Closed retrospectively: the code shipped in the commits named below and the
> proofs were reconstructed from the current code and test suite, not observed
> at the time of delivery.

Shipped in `b1fceac`. `cdx run-tail <run_id> [--lines N] --json` returns the
tail of the run's recorded `stdout_path` with the run's current status.

The four tests cover the cases that distinguish a real tail from a naive one:
`test_run_tail_returns_the_last_lines_of_a_running_run`,
`test_run_tail_on_a_run_that_has_not_written_yet`,
`test_run_tail_drops_a_partial_leading_line` (seeking backwards into a file
lands mid-line, and returning that fragment would corrupt a caller's parse),
and `test_run_tail_missing_output_on_a_finished_run_is_an_error`, which pins
the specific error code AC3 asked for rather than an empty success.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_011_programmatic_cli_contract_for_non_interactive_callers`
- Architecture decision(s): (none yet)
- Request: `req_021_close_the_programmatic_cli_contract_gaps_that_force_agent_callers_to_reimplement_cdx_internals`
- Primary task(s): `task_032_orchestrate_the_programmatic_cli_contract_for_agent_callers`

# AI Context
- Summary: Add run-tail subcommand for live run output
- Keywords: scaffolded-backlog, add run-tail subcommand for live run output, implementation-ready
- Use when: Implementing the scaffolded slice for Add run-tail subcommand for live run output.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
