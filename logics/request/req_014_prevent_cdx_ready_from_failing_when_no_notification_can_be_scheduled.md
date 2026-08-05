## req_014_prevent_cdx_ready_from_failing_when_no_notification_can_be_scheduled - Prevent cdx ready from failing when no notification can be scheduled
> From version: 0.12.1
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Complexity: Low
> Theme: CLI reliability
> Reminder: Update status/understanding/confidence and linked backlog/task references when you edit this doc.
> Indicators reviewed: 2026-08-05

# Needs
- Operators need `cdx ready` to finish predictably when there is no eligible future reset, rather than terminating with an uncaught-looking scheduling failure.

# Context
- `cdx ready` is a shortcut for `cdx notify --next-ready --schedule`.
- When no cooling-down eligible session has a future reset, `resolve_notify_event` returns a non-ready event without `target_timestamp`; the scheduler currently rejects that event.
- The underlying scheduled-notification path is shared, so the fix must preserve normal OS scheduling and immediate-ready notification behavior.

# Acceptance criteria
- AC1: `cdx ready` with no eligible upcoming reset exits successfully and emits a clear, non-error result explaining that no notification was scheduled.
- AC2: `cdx ready --json` in that case returns the normal successful notify envelope, keeps the resolved event message, and includes an explicit schedule result with `scheduled: false` instead of an exception or traceback.
- AC3: `cdx notify --next-ready --schedule` has the same safe no-target behavior, while a named `--at-reset` notification with no known reset retains its actionable error contract.
- AC4: Existing future-reset scheduling still selects the correct backend and registers one job; already-due targets still notify immediately without creating a job.
- AC5: Focused CLI and notification tests cover no sessions, only currently usable sessions, missing reset timestamps, future reset, already-due reset, text output, and JSON output.

# Definition of Ready (DoR)
- [x] Problem statement is explicit and user impact is clear.
- [x] Scope boundaries (in/out) are explicit.
- [x] Acceptance criteria are testable.
- [x] Dependencies and known risks are listed.

# Companion docs
- Product brief(s): `prod_007_reliable_next_ready_notification_shortcut`
- Architecture decision(s): (none yet)

# References
- GitHub issue #1
- src/cli.py
- src/cli_commands.py::handle_notify
- src/notify.py::schedule_notification_event
- test/test_cli_py.py
- test/test_notify_py.py

# AI Context
- Summary: Prevent cdx ready from failing when no notification can be scheduled
- Keywords: request-chain-scaffold, prevent cdx ready from failing when no notification can be scheduled, development-ready
- Use when: You need to implement or review the scaffolded workflow for Prevent cdx ready from failing when no notification can be scheduled.
- Skip when: The change is unrelated to this scaffolded request chain.

# Backlog
- `item_034_handle_no_target_cdx_ready_scheduling_gracefully`

# AC Traceability
- request-AC1 -> Task `task_025_orchestrate_safe_cdx_ready_no_target_handling`. Proof: no-target next-ready scheduling returns a successful non-scheduled result.
- request-AC2 -> Task `task_025_orchestrate_safe_cdx_ready_no_target_handling`. Proof: JSON output includes the normal notify envelope with `scheduled: false`.
- request-AC3 -> Task `task_025_orchestrate_safe_cdx_ready_no_target_handling`. Proof: next-ready schedule shares safe no-target behavior while named reset errors remain actionable.
- request-AC4 -> Task `task_025_orchestrate_safe_cdx_ready_no_target_handling`. Proof: future reset and already-due reset scheduling paths remain covered.
- request-AC5 -> Task `task_025_orchestrate_safe_cdx_ready_no_target_handling`. Proof: focused CLI and notification regression tests cover no-target, future, due, text, and JSON behavior.
