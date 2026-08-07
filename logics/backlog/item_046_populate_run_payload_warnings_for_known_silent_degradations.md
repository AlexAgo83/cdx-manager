## item_046_populate_run_payload_warnings_for_known_silent_degradations - Populate run payload warnings for known silent degradations
> From version: 0.12.4
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Low
> Theme: Agent integration surface
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-07

# Problem
- `run_result_payload()` in `src/run_command.py:107` hardcodes `"warnings": []`. It is the only occurrence of the key in that module, so the run payload's warning channel is declared in the contract and never carries anything.
- Meanwhile a known silent degradation is reported nowhere. On Codex-backed sessions the provider's sandbox ties network access to the permission level, so a run below `full` cannot resolve DNS for network tools invoked inside it. The run still exits zero and reports success; the caller discovers the failed network work only by reading the transcript.
- The knowledge exists, but only as prose in a downstream caller's docstring rather than as data cdx emits, so every caller must rediscover it. It was in fact rediscovered the hard way while auditing this CLI on 2026-08-05.
- `handle_status()` already composes a `warnings` list for its own payload (`src/cli_commands.py:2338` onward), so the pattern to follow exists in the codebase; `run` simply never adopted it.

# Scope
- In:
  - Populate the run payload's `warnings` list instead of hardcoding it empty, keeping the existing entry shape used elsewhere in the CLI so callers see one consistent warning structure.
  - Emit a warning when a run is launched at a permission level that is known to disable provider network access, naming the provider, the effective permission, and the consequence.
  - Derive the condition from the provider and effective permission already resolved during the run, not from a separately maintained table that could drift from the launch mapping.
  - Emit the warning on the successful path as well as the failure path, since the whole point is that the run appears to succeed.
  - Include the warning in the detached launch payload from `item_041` where the condition is known at launch time, so a non-blocking caller is not the only one left uninformed.
  - Document the warning channel in the README's programmatic-caller section as a field that callers should surface rather than discard.
  - Add tests asserting the warning is present for a network-restricted Codex run, absent when the permission does not restrict network access, and absent for providers with no such coupling.
- Out:
  - No new warning severity levels or per-warning suppression flags.
  - No change to exit codes, `ok`, or any error field; a warning never turns a success into a failure.
  - No audit of every possible provider degradation in this slice; the network-below-full case is the one confirmed by the audit, and the mechanism it introduces is what later cases reuse.
  - No change to the permission-to-provider-flag mapping itself.

# Acceptance criteria
- Given a Codex-backed run launched at a permission level that disables provider network access, the run payload's `warnings` list contains an entry naming the provider, the effective permission, and the loss of network access.
- Given that same run exits successfully, `ok` remains true, the exit code is unchanged, and the warning is still present.
- Given a run at a permission level that does not restrict network access, the `warnings` list contains no network entry.
- Given a provider whose permission model has no network coupling, no network warning is emitted regardless of permission.
- Given a detached launch from `item_041` where the condition is determinable at launch, the launch-time payload carries the same warning.
- Warning entries use the same structural shape as the warnings already emitted by `cdx status`, so a caller parses one shape across subcommands.
- No test asserts an empty `warnings` list as the expected value for a run that meets a warning condition.

# AC Traceability
- request-AC10 -> This backlog slice. Proof: Given a Codex-backed run launched at a permission level that disables provider network access, the run payload's `warnings` list contains an entry naming the provider, the effective permission, and the loss of network access.
- request-AC8 -> This backlog slice. Proof: Given that same run exits successfully, `ok` remains true, the exit code is unchanged, and the warning is still present.
- request-AC9 -> This backlog slice. Proof: The README's programmatic-caller section documents the warning channel as a field callers should surface rather than discard.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_011_programmatic_cli_contract_for_non_interactive_callers`
- Architecture decision(s): (none yet)
- Request: `req_021_close_the_programmatic_cli_contract_gaps_that_force_agent_callers_to_reimplement_cdx_internals`
- Primary task(s): `task_032_orchestrate_the_programmatic_cli_contract_for_agent_callers`

# AI Context
- Summary: Populate run payload warnings for known silent degradations
- Keywords: scaffolded-backlog, populate run payload warnings for known silent degradations, implementation-ready
- Use when: Implementing the scaffolded slice for Populate run payload warnings for known silent degradations.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: Medium
- Rationale: A dead field in a shipped contract; low effort, but it turns a silently-degraded successful run into a reportable one for every caller.
