## req_017_investigate_missing_cdx_run_registry_entry_after_provider_capacity_failure - Investigate missing cdx run registry entry after provider capacity failure
> From version: 0.12.2
> Schema version: 1.0
> Status: Draft
> Understanding: 90%
> Confidence: 85%
> Complexity: Medium
> Theme: Run observability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.

# Needs
- A `cdx run` that executes real provider work must always be observable through the run registry once the CLI has accepted the invocation and reached the pre-launch registration point.
- Operators need `cdx runs`, `cdx run-status`, and `cdx run-report` to be reliable for monitoring in-progress and recently failed runs, including provider-side capacity failures.
- A missing registry entry after visible tool execution should be treated as a run lifecycle reliability bug, not as an expected `run_not_found` outcome.

# Context
- GitHub issue #6 reports run `98130e82a2734dabaace7257eb167abc`, observed on 2026-08-05.
- Disk artifacts existed under `~/.cdx/profiles/main/log/cdx-run-98130e82a2734dabaace7257eb167abc.{stdout,stderr}.log`; stdout contained multiple real JSON events and ended with `Selected model is at capacity. Please try a different model.`
- `cdx run-status 98130e82a2734dabaace7257eb167abc --json` returned `run_not_found`, and `~/.cdx/runs.json` had no matching entry.
- Existing registry work exists in `req_005_add_observable_assistant_run_registry_and_structured_task_reports`, `item_017_add_observable_assistant_run_registry_and_structured_task_reports`, and `task_017_add_observable_assistant_run_registry_and_structured_task_reports`, but those docs are Done and describe the intended baseline contract rather than this regression investigation.

# Acceptance criteria
- AC1: A reproducible or fixture-backed scenario demonstrates a provider subprocess that emits real stdout events and then fails with a provider capacity error.
- AC2: The run registry contains a `running` entry before provider execution starts, and the same `run_id` remains queryable after the capacity failure.
- AC3: The terminal registry state for this failure is explicit, non-successful, and includes an actionable provider error summary without reporting `run_not_found`.
- AC4: `cdx runs`, `cdx run-status <run_id> --json`, and `cdx run-report <run_id> --json` agree on the run identity, status, artifacts, and error fields for the failed run.
- AC5: Tests cover the failing path without requiring a live provider capacity event.
- AC6: The investigation identifies why the reported run skipped persistence, or narrows the root cause to a documented untestable external condition with evidence.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# References
- GitHub issue #6
- `src/cli_commands.py::handle_run`
- `src/run_registry.py`
- `src/provider_runtime.py`
- `src/run_command.py`
- `test/test_cli_py.py`
- Existing baseline corpus: `req_005_add_observable_assistant_run_registry_and_structured_task_reports`, `item_017_add_observable_assistant_run_registry_and_structured_task_reports`, `task_017_add_observable_assistant_run_registry_and_structured_task_reports`

# AI Context
- Summary: Ensure `cdx run` registry persistence survives provider capacity failures after real execution starts.
- Keywords: GitHub issue #6, cdx run, run registry, run_not_found, provider capacity, failed turn, artifacts, runs.json
- Use when: Investigating or fixing missing run registry entries for failed headless runs.
- Skip when: Work is only about adding new run report fields unrelated to registry persistence.

# Backlog
- none
- `item_037_investigate_missing_cdx_run_registry_entry_after_provider_capacity_failure`
