## item_138_drain_codex_app_server_diagnostic_stderr_safely - Drain Codex app-server diagnostic stderr safely
> From version: 0.20.4
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Low
> Theme: Reliability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.
> Indicators reviewed: 2026-08-22 14:15:49

# AI Context
- Summary: Remove stderr backpressure from the bounded app-server diagnostic path without exposing provider output.
- Keywords: drain, codex, app, server, diagnostic, stderr, safely
- Use when: A JSON-RPC provider probe pipes output from a child process.
- Skip when: Publishing provider diagnostics or changing the JSON-RPC request contract.

# Problem
- The app-server probe pipes stderr without consuming it, which can block a child process before the expected stdout response arrives.

# Scope
- In:
  - Use the smallest safe stderr handling path for the existing subprocess lifecycle.
  - Cover a noisy stderr response and preserve existing timeout and cleanup behavior.
- Out:
  - Returning provider stderr to CLI users or changing authentication result payloads.

# Acceptance criteria
- AC1: A simulated app-server can write stderr and still return the expected stdout JSON-RPC response.
- AC2: The probe retains its bounded timeout and cleanup behavior.
- AC3: No provider stderr is surfaced to callers.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: A simulated app-server can write stderr and still return the expected stdout JSON-RPC response.
- request-AC2 -> This backlog slice. Proof: AC2: The probe retains its bounded timeout and cleanup behavior.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_052_reliable_codex_diagnostics_in_packaged_installs`
- Architecture decision(s): (none yet)
- Request: `req_069_harden_codex_probe_process_and_package_smoke_coverage`
- Primary task(s): `task_078_orchestrate_reliable_codex_diagnostics_and_package_smokes`

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.

# Tasks
- `task_078_orchestrate_reliable_codex_diagnostics_and_package_smokes`

# Notes
- Task `task_078_orchestrate_reliable_codex_diagnostics_and_package_smokes` was finished via `logics-manager flow finish task` on 2026-08-22.
