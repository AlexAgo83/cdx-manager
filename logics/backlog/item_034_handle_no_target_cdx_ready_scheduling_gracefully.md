## item_034_handle_no_target_cdx_ready_scheduling_gracefully - Handle no-target cdx ready scheduling gracefully
> From version: 0.12.1
> Schema version: 1.0
> Status: Done
> Understanding: 90%
> Confidence: 85%
> Progress: 100%
> Complexity: Low
> Theme: CLI reliability
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# Problem
- A valid no-upcoming-reset result reaches scheduling without a target timestamp and becomes a command failure.
- The shortcut needs a stable text and JSON outcome that automation can distinguish from a scheduled job.

# Scope
- In:
  - Define the no-target schedule result at the shared notify scheduling boundary.
  - Route `cdx ready` and next-ready scheduled notify through that result.
  - Add focused regression tests and update help/README only if output semantics require documentation.
- Out:
  - Provider status refresh changes.
  - Retry/poll loops, notification backend additions, or changes to named at-reset error semantics.

# Acceptance criteria
- AC1: A no-target next-ready schedule returns a non-scheduled result, not `CdxError`.
- AC2: JSON exposes `scheduled: false` and a stable backend/reason field suitable for automation.
- AC3: Existing scheduled and immediate event paths remain regression-covered.
- AC4: Named at-reset requests with no reset time remain errors with their current guidance.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: A no-target next-ready schedule returns a non-scheduled result, not `CdxError`.
- request-AC2 -> This backlog slice. Proof: AC2: JSON exposes `scheduled: false` and a stable backend/reason field suitable for automation.
- request-AC3 -> This backlog slice. Proof: AC3: Existing scheduled and immediate event paths remain regression-covered.
- request-AC4 -> This backlog slice. Proof: AC4: Named at-reset requests with no reset time remain errors with their current guidance.
- request-AC5 -> This backlog slice. Proof: AC4: Named at-reset requests with no reset time remain errors with their current guidance.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_007_reliable_next_ready_notification_shortcut`
- Architecture decision(s): (none yet)
- Request: `req_014_prevent_cdx_ready_from_failing_when_no_notification_can_be_scheduled`
- Primary task(s): `task_025_orchestrate_safe_cdx_ready_no_target_handling`

# AI Context
- Summary: Handle no-target cdx ready scheduling gracefully
- Keywords: scaffolded-backlog, handle no-target cdx ready scheduling gracefully, implementation-ready
- Use when: Implementing the scaffolded slice for Handle no-target cdx ready scheduling gracefully.
- Skip when: The change belongs to another backlog slice.

# Priority
- Priority: High
- Rationale: Set by scaffold input or defaulted for grooming.

# Notes
- Task `task_025_orchestrate_safe_cdx_ready_no_target_handling` was finished via `logics-manager flow finish task` on 2026-08-05.
