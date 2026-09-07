## item_148_make_accepted_local_writes_and_run_processes_owned_by_cdx - Make accepted local writes and run processes owned by CDX
> From version: 0.20.9
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Medium
> Theme: Process lifecycle
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-07 09:59:28

# AI Context
- Summary: Implements the local-write and run-lifecycle slice for req_073 findings 4-6: concurrent memory append retention, detached CLI child module resolution, and interrupt cleanup for owned provider processes.
- Keywords: req_073, context_store, append_context_path, runs detach, provider_runtime, KeyboardInterrupt, SIGINT, process cleanup
- Use when: Changing memory append semantics, detached headless runs, or provider child process ownership.
- Skip when: The work is about credential import, encrypted backup KDFs, tray installation, or WSL terminal interop.

# Problem
- Concurrent memory appends can lose accepted notes, detached runs invoke a nonexistent module, and interrupted headless runs can leave providers alive.

# Scope
- In:
  - Serialize context memory read-modify-write for the existing append helper.
  - Fix detached child argv and package root resolution for source/npm and installed Python layouts.
  - Terminate and reap owned provider processes on supervisor interruption and record cancellation.
  - Add one focused regression per defect using synthetic providers and temporary state.
- Out:
  - No distributed memory service, no new run scheduler, no provider CLI behavior changes, and no real provider generation during tests.

# Acceptance criteria
- AC1: Two concurrent successful memory appends preserve both notes.
- AC2: A real detached child reaches a synthetic provider and records a terminal result.
- AC3: SIGINT cleanup terminates and reaps the owned provider child and records cancellation.

# AC Traceability
- request-AC4 -> This backlog slice. Proof: `test/test_context_store_py.py::test_concurrent_appends_keep_every_accepted_note` — three concurrent appends and the pre-existing content all survive; the test loses a note without the serialization.
- request-AC5 -> This backlog slice. Proof: `test/test_commands_runs_py.py::test_detached_child_runs_the_cli_module_and_records_a_terminal_result` (real detached child, synthetic provider on PATH, `succeeded` registry record) and `::test_detached_child_command_names_the_top_level_cli_module` (source and installed package layouts).
- request-AC6 -> This backlog slice. Proof: `test/test_commands_runs_py.py::test_interrupting_a_headless_run_kills_the_provider_and_records_cancellation` — the real provider process group is terminated and reaped, and the run settles as `cancelled`.
- request-AC13 -> This backlog slice. Proof: `python3 -m pytest -q` (1,020 passed) and `npm run lint` (all checks passed) after the slice.
> Shared proof: request-AC6 and request-AC13 share the same final validation wave for this slice.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Implementation
- `src/context_store.py`: per-path lock around the append read-modify-write, so parallel agents cannot lose an accepted note.
- `src/commands/runs.py`: `_cdx_self_command` names the top-level CLI module and walks out of every package component to find the import root, and fails the launch when the module does not resolve; the cancelled path records its own terminal status.
- `src/provider_runtime.py`: a headless wait interrupted by Ctrl-C terminates and reaps the provider process group and raises a cancellation carrying run info.

# Links
- Product brief(s): `prod_054_recoverable_cdx_operations_across_credentials_runs_and_tray_interop`
- Architecture decision(s): (none yet)
- Request: `req_074_harden_review_findings_for_credential_safety_process_lifecycle_and_tray_interop`
- Primary task(s): `task_082_orchestrate_review_finding_hardening_across_credentials_runs_and_tray_interop`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.

# Tasks
- `task_082_orchestrate_review_finding_hardening_across_credentials_runs_and_tray_interop`

# Notes
- Task `task_082_orchestrate_review_finding_hardening_across_credentials_runs_and_tray_interop` was finished via `logics-manager flow finish task` on 2026-09-07.
