## item_091_alert_on_claude_turns_that_end_in_a_provider_error - Alert on Claude turns that end in a provider error
> From version: 0.18.4
> Schema version: 1.0
> Status: Done
> Understanding: 85
> Confidence: 80
> Progress: 100%
> Complexity: Medium
> Theme: Desktop integration
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: Carry a failed agent turn into the tray, using the error class the provider already publishes.
- Keywords: StopFailure, failed turn, rate limit, tray alert, provider hooks
- Use when: Extending the structured alert envelope to turns that end in a provider error.
- Skip when: Working on completion or permission alerts, which item_086 owns.

# Problem
- A turn killed by a provider error produces no alert, so the session simply goes quiet and the user finds out by looking at the terminal.
- Claude Code publishes the classification needed to say why (StopFailure, carrying error_type and error_message), and nothing subscribes to it.
- Codex publishes no documented equivalent, so a naive implementation would imply a parity that does not exist.

# Scope
- In:
  - Provision the Claude failure hook alongside the existing Stop and PermissionRequest subscriptions.
  - Carry the error class through the structured envelope introduced by item_086, reusing its sanitization boundary.
  - Distinguish transient from actionable failures in the rendered alert, and word it so it cannot read as a completion.
  - State the missing Codex equivalent in user-facing documentation.
  - Add focused Python and Rust coverage.
- Out:
  - Retrying, resuming, or otherwise acting on the failed turn.
  - Any new envelope version or transport beyond what item_086 delivers.
  - Provider-side error handling, quota policy, or capacity display changes.

# Acceptance criteria
- AC1: A Claude turn ending in a provider error produces exactly one tray alert naming the session, the project, and the error class.
- AC2: Transient and actionable failures are distinguishable, and no failure alert reads as a completion.
- AC3: error_message follows the existing preview preference, normalization, and bound; error_type is always available as safe metadata.
- AC4: A failed turn produces no completion alert and a completed turn produces no failure alert, including when both hooks fire for one turn.
- AC5: The absence of a Codex equivalent is documented rather than presented as parity.
- AC6: Focused tests and the project validation suite pass.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: A Claude turn ending in a provider error produces exactly one tray alert naming the session, the project, and the error class.
- request-AC2 -> This backlog slice. Proof: AC2: Transient and actionable failures are distinguishable, and no failure alert reads as a completion.
- request-AC3 -> This backlog slice. Proof: AC3: error_message follows the existing preview preference, normalization, and bound; error_type is always available as safe metadata.
- request-AC4 -> This backlog slice. Proof: AC4: A failed turn produces no completion alert and a completed turn produces no failure alert, including when both hooks fire for one turn.
- request-AC5 -> This backlog slice. Proof: AC5: The absence of a Codex equivalent is documented rather than presented as parity.
- request-AC6 -> This backlog slice. Proof: AC6: Focused tests and the project validation suite pass.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
- Request: `req_044_alert_on_agent_turns_that_fail_before_completion`
- Primary task(s): `task_055_orchestrate_alerts_for_failed_agent_turns`

# Priority
- Priority: Low
- Rationale: Real coverage gap, but it waits on the structured envelope from item_086 rather than competing with it.

# Notes
- Depends on item_086: the envelope it introduces is what a failure would travel in.
- Task `task_055_orchestrate_alerts_for_failed_agent_turns` was finished via `logics-manager flow finish task` on 2026-08-11.

# Tasks
- `task_055_orchestrate_alerts_for_failed_agent_turns`
