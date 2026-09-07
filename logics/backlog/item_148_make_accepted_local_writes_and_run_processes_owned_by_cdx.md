## item_148_make_accepted_local_writes_and_run_processes_owned_by_cdx - Make accepted local writes and run processes owned by CDX
> From version: 0.20.9
> Schema version: 1.0
> Status: In progress
> Understanding: 90%
> Confidence: 85%
> Progress: 25%
> Complexity: Medium
> Theme: Process lifecycle
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-09-07 09:39:34

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
- request-AC4 -> This backlog slice. Proof: AC1: Two concurrent successful memory appends preserve both notes.
- request-AC5 -> This backlog slice. Proof: AC2: A real detached child reaches a synthetic provider and records a terminal result.
- request-AC6 -> This backlog slice. Proof: AC3: SIGINT cleanup terminates and reaps the owned provider child and records cancellation.
- request-AC13 -> This backlog slice. Proof: AC3: SIGINT cleanup terminates and reaps the owned provider child and records cancellation.
> Shared proof: request-AC6 and request-AC13 share the same final validation wave for this slice.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_054_recoverable_cdx_operations_across_credentials_runs_and_tray_interop`
- Architecture decision(s): (none yet)
- Request: `req_074_harden_review_findings_for_credential_safety_process_lifecycle_and_tray_interop`
- Primary task(s): `task_082_orchestrate_review_finding_hardening_across_credentials_runs_and_tray_interop`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.
