## task_028_investigate_missing_cdx_run_registry_entry_after_provider_capacity_failure - Investigate missing cdx run registry entry after provider capacity failure
> From version: 0.12.2
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Definition of Done (DoD)
- [ ] The backlog scope is implemented.
- [ ] Acceptance criteria are covered.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# Backlog
- `item_037_investigate_missing_cdx_run_registry_entry_after_provider_capacity_failure`

# Acceptance criteria
- AC1: The failing path is covered by a test that would have caught a run with log artifacts but no registry entry.
- AC2: `registry.start(...)` is guaranteed for every accepted run before provider subprocess dispatch, including named-session and provider-explicit paths after authentication succeeds.
- AC3: Provider capacity failure after stdout activity records a terminal failed/error status with `run_id`, cwd, provider/session metadata, artifact paths, exit information when available, and the capacity message.
- AC4: `cdx run-status <run_id> --json` never returns `run_not_found` for the simulated accepted run.
- AC5: `cdx runs --json` includes the failed run, and `cdx run-report <run_id> --json` exposes the same artifacts and error summary.
- AC6: Existing success, validation-error, timeout, cancellation, and stale-process registry tests continue to pass.

# Plan
- [ ] 1. Reconstruct the issue #6 lifecycle from `handle_run`, registry writes, provider dispatch, and finalization paths.
- [ ] 2. Add or extend a fake provider/runtime test that emits stdout JSON events and then fails with `Selected model is at capacity. Please try a different model.`
- [ ] 3. Fix the smallest lifecycle gap that can leave an accepted run without a registry entry or erase the entry during failure handling.
- [ ] 4. Assert `runs`, `run-status`, and `run-report` JSON behavior for the simulated failed run.
- [ ] 5. Run focused run-registry/CLI tests plus Logics lint before closeout.
- [ ] 6. Record the root cause and any non-reproducible external assumptions in the implementation report.

# Validation
- Planned: focused run registry and CLI tests covering provider capacity failure.
- Planned: `logics-manager lint --require-status`.

# Report
- Not started.

# AI Context
- Summary: Implement the regression fix for accepted failed `cdx run` invocations missing from the registry.
- Keywords: GitHub issue #6, cdx run, run registry, run_not_found, provider capacity, failed provider subprocess
- Use when: Working the implementation task for missing run registry entries after provider failures.
- Skip when: The work is only about unrelated CLI argument validation or release checksum automation.

# Links
- Request: `req_017_investigate_missing_cdx_run_registry_entry_after_provider_capacity_failure`
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)

# AC Traceability
- request-AC1 -> Task AC1. Proof: provider capacity failure fixture includes stdout activity.
- request-AC2 -> Task AC2, Task AC3, Task AC4. Proof: accepted runs are registered before dispatch and remain queryable.
- request-AC3 -> Task AC3. Proof: failed terminal state carries the provider capacity error.
- request-AC4 -> Task AC4, Task AC5. Proof: list/status/report surfaces agree.
- request-AC5 -> Task AC1. Proof: tests avoid live provider capacity.
- request-AC6 -> Task plan step 6. Proof: implementation report documents the root cause or bounded external condition.
