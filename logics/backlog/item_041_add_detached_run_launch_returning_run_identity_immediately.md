## item_041_add_detached_run_launch_returning_run_identity_immediately - Add detached run launch returning run identity immediately
> From version: 0.12.4
> Schema version: 1.0
> Status: Done
> Understanding: 100%
> Confidence: 100%
> Progress: 90%
> Complexity: Medium
> Theme: Agent integration surface
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- `handle_run()` always blocks for the full duration of the provider process, so a caller with its own per-call timeout cannot launch anything long-running even though the run itself would succeed server-side.
- `run_id` is computed at `src/cli_commands.py:1058` and registered before the provider starts, but is only emitted after completion, so a caller that launches a run has no way to name it.
- Downstream this is worked around by spawning cdx via `Popen` with a detached session and a caller-managed log file, then polling `cdx runs` for up to 8 seconds to guess the run id by matching session, cwd, running status and absence from a pre-launch snapshot. The guess returns nothing when authentication is slow, and the whole mechanism is unavailable over SSH.

# Scope
- In:
  - Add a `--detach` flag to `cdx run` argument parsing in `src/cli_args.py`, rejected in combination with any option whose meaning depends on waiting for completion.
  - In `handle_run()`, after `registry.start()` has registered the run, branch on `--detach`: launch the provider process detached from the invoking process, write a success payload carrying `run_id` and the artifact paths, and return without awaiting the provider.
  - Ensure the detached child survives the parent exiting in a non-interactive SSH context, not only in a local shell.
  - Ensure the registry entry for a detached run is still transitioned to a terminal status by the detached process itself, so `runs`/`run-status` remain accurate without the launching process.
  - Emit `run_id` in the launch-time payload for the detached path, and confirm the blocking path continues to report the same `run_id` it always did.
  - Add tests covering: detached launch returns a payload with a non-null `run_id` promptly, the run appears in `cdx runs` immediately after launch, the detached run reaches a terminal status, and the non-detached path is unchanged.
- Out:
  - No process supervision, restart, or cancellation feature for detached runs.
  - No change to how artifact paths are computed.
  - No new notification or callback mechanism on completion.

# Acceptance criteria
- Given a valid session and cwd, `cdx run <session> --cwd <path> --prompt-file <file> --detach --json` returns within seconds with `ok: true` and a non-null `run_id`, while the provider is still executing.
- Given a detached launch, `cdx run-status <run_id> --json` immediately reports the run as running and later reports a terminal status without any further involvement from the launching process.
- Given a detached launch whose parent process exits immediately afterwards, the provider process continues and the run still reaches a terminal status.
- Given `--detach` combined with an option that only has meaning when waiting for completion, the command fails before launching anything, with a specific error code.
- Given a run launched without `--detach`, the command still blocks and returns the existing completion payload unchanged, including `usage` and artifact paths.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: Given a valid session and cwd, `cdx run <session> --cwd <path> --prompt-file <file> --detach --json` returns within seconds with `ok: true` and a non-null `run_id`, while the provider is still executing.
- request-AC2 -> This backlog slice. Proof: Given a detached launch, `cdx run-status <run_id> --json` immediately reports the run as running and later reports a terminal status without any further involvement from the launching process.
- request-AC8 -> This backlog slice. Proof: Given a detached launch whose parent process exits immediately afterwards, the provider process continues and the run still reaches a terminal status.

# Outcome

> Closed retrospectively: the code shipped in the commits named below and the
> proofs were reconstructed from the current code and test suite, not observed
> at the time of delivery.

Shipped in `b1fceac`, corrected in `81a0c7a`. `cdx run --detach --json`
registers the run, launches the provider detached, and returns immediately
with the `run_id`. The detached child transitions its own registry entry to a
terminal status, so `cdx runs` and `cdx run-status` stay accurate with nobody
supervising.

Covered by `test_run_detach_returns_run_id_without_waiting`,
`test_detached_run_id_is_consumed_not_inherited` and
`test_detached_child_deletes_the_staged_prompt_file`.

Worth recording honestly: the Windows detachment branch was flagged at
delivery as unverifiable, since the tests asserted the POSIX
`start_new_session` unconditionally. That assertion was fixed in `49c6eaf`
during a later session, and the Windows CI job now exercises the
`creationflags` path. The spawn is stubbed there, so it proves the flags are
chosen correctly, not that a child actually survives on Windows.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_011_programmatic_cli_contract_for_non_interactive_callers`
- Architecture decision(s): (none yet)
- Request: `req_021_close_the_programmatic_cli_contract_gaps_that_force_agent_callers_to_reimplement_cdx_internals`
- Primary task(s): `task_032_orchestrate_the_programmatic_cli_contract_for_agent_callers`

# AI Context
- Summary: Add detached run launch returning run identity immediately
- Keywords: scaffolded-backlog, add detached run launch returning run identity immediately, implementation-ready
- Use when: Implementing the scaffolded slice for Add detached run launch returning run identity immediately.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
