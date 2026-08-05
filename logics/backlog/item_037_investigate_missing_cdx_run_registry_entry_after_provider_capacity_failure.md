## item_037_investigate_missing_cdx_run_registry_entry_after_provider_capacity_failure - Investigate missing cdx run registry entry after provider capacity failure
> From version: 0.12.2
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: High
> Theme: Operator workflow and runtime integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- A `cdx run` reached real provider execution and produced log artifacts, but the run was absent from `~/.cdx/runs.json` and returned `run_not_found`.
- This contradicts the expected lifecycle in which `registry.start(...)` runs before provider dispatch.
- Monitoring tools cannot trust `cdx runs` or `cdx run-status` if accepted, executing runs can disappear after provider-side capacity failures.

# Scope
- In:
  - Audit the accepted `cdx run` path from argument parsing through authentication, registry start, provider launch, subprocess failure handling, and final registry update.
  - Add a deterministic regression test using a fake provider/runtime path that writes realistic stdout events and then fails with the capacity message.
  - Preserve artifact paths and terminal error details in the registry entry when the provider fails mid-turn.
  - Verify `runs`, `run-status`, and `run-report` behavior against the same failed run.
- Out:
  - Changing provider quota/capacity behavior or retry policy.
  - Redesigning the run registry schema beyond fields needed to preserve the existing contract.
  - Reopening the completed observable run registry baseline corpus except as historical context.

# Acceptance criteria
- AC1: The failing path is covered by a test that would have caught a run with log artifacts but no registry entry.
- AC2: `registry.start(...)` is guaranteed for every accepted run before provider subprocess dispatch, including named-session and provider-explicit paths after authentication succeeds.
- AC3: Provider capacity failure after stdout activity records a terminal failed/error status with `run_id`, cwd, provider/session metadata, artifact paths, exit information when available, and the capacity message.
- AC4: `cdx run-status <run_id> --json` never returns `run_not_found` for the simulated accepted run.
- AC5: `cdx runs --json` includes the failed run, and `cdx run-report <run_id> --json` exposes the same artifacts and error summary.
- AC6: Existing success, validation-error, timeout, cancellation, and stale-process registry tests continue to pass.

# AC Traceability
- request-AC1 -> AC1. Proof: A fixture-backed provider capacity failure reproduces stdout activity followed by failure.
- request-AC2 -> AC2, AC3, AC4. Proof: Accepted runs are registered before provider dispatch and remain queryable after failure.
- request-AC3 -> AC3. Proof: Terminal state records the capacity message and failed status.
- request-AC4 -> AC4, AC5. Proof: Status, list, and report surfaces agree on the same run record.
- request-AC5 -> AC1. Proof: The regression uses a fake provider/runtime path, not live capacity.
- request-AC6 -> AC1, AC2. Proof: The investigation must identify or bound the persistence gap.

# Decision framing
- Product framing: Not needed
- Product signals: (none detected)
- Product follow-up: No product brief follow-up is expected based on current signals.
- Architecture framing: Not needed
- Architecture signals: (none detected)
- Architecture follow-up: No architecture decision follow-up is expected based on current signals.

# Links
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
- Request: `req_017_investigate_missing_cdx_run_registry_entry_after_provider_capacity_failure`
- Primary task(s): `task_028_investigate_missing_cdx_run_registry_entry_after_provider_capacity_failure`

# AI Context
- Summary: Fix the gap where a real failed `cdx run` can have artifacts but no run registry entry.
- Keywords: GitHub issue #6, cdx run, run registry, run_not_found, provider capacity, registry.start, runs.json
- Use when: Implementing or reviewing the missing-registry-entry regression for failed headless runs.
- Skip when: The change is only about report formatting for runs that are already registered.

# Priority
- Priority: High
- Rationale: Run observability is a reliability contract for automation; disappearing failed runs break monitoring and incident diagnosis.

# Notes
- Hybrid rationale: Derived from request `req_017_investigate_missing_cdx_run_registry_entry_after_provider_capacity_failure` and kept bounded to one coherent delivery slice.
- Source file: `logics/request/req_017_investigate_missing_cdx_run_registry_entry_after_provider_capacity_failure.md`.
- Generated locally by logics-manager.
- Related existing corpus is Done and broader: `req_005_add_observable_assistant_run_registry_and_structured_task_reports`, `item_017_add_observable_assistant_run_registry_and_structured_task_reports`, `task_017_add_observable_assistant_run_registry_and_structured_task_reports`.

# Tasks
- `task_028_investigate_missing_cdx_run_registry_entry_after_provider_capacity_failure`
