## task_055_orchestrate_alerts_for_failed_agent_turns - Orchestrate alerts for failed agent turns
> From version: 0.18.4
> Schema version: 1.0
> Status: Draft
> Understanding: 85
> Confidence: 80
> Progress: 0
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# AI Context
- Summary: Carry a turn that dies on a provider error into the tray, after the structured envelope exists.
- Keywords: StopFailure, failed turn, tray alert, provider hooks, orchestration
- Use when: Delivering the failure-alert slice once item_086 has landed.
- Skip when: Working on completion or permission alerts.

# Context
- Execute the bounded delivery slice for alerts on agent turns that end in a provider error.
- Sequenced behind task_050: the structured envelope introduced there is what a failure travels in, and starting first would mean designing a second transport.
- Claude Code publishes StopFailure with error_type and error_message. Codex publishes no documented equivalent, so this is a Claude-only alert that has to say so rather than imply parity.
- error_type is a closed enum and safe metadata; error_message is provider free text and follows the same preview preference, normalization, and bound as assistant text.

# Plan
- [ ] 1. Confirm that the structured envelope from task_050 has landed and can carry a failure without a new version.
- [ ] 2. Provision the Claude failure hook alongside the existing subscriptions, and keep cdx notify silent on stdout as that work established.
- [ ] 3. Render transient and actionable failures distinguishably, with wording that cannot read as a completion.
- [ ] 4. Add focused tests for each error class, the preview boundary, and mutual exclusion with completion alerts; document the missing Codex equivalent.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_091_alert_on_claude_turns_that_end_in_a_provider_error`

# Definition of Done (DoD)
- [ ] Code is implemented and reviewed.
- [ ] Validation passes.
- [ ] Linked docs are synchronized.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_091_alert_on_claude_turns_that_end_in_a_provider_error`. Proof deferred to slice closeout.
- request-AC2 -> `item_091_alert_on_claude_turns_that_end_in_a_provider_error`. Proof deferred to slice closeout.
- request-AC3 -> `item_091_alert_on_claude_turns_that_end_in_a_provider_error`. Proof deferred to slice closeout.
- request-AC4 -> `item_091_alert_on_claude_turns_that_end_in_a_provider_error`. Proof deferred to slice closeout.
- request-AC5 -> `item_091_alert_on_claude_turns_that_end_in_a_provider_error`. Proof deferred to slice closeout.
- request-AC6 -> `item_091_alert_on_claude_turns_that_end_in_a_provider_error`. Proof deferred to slice closeout.
- backlog-AC1 -> This task. Proof: task remains bounded to the linked backlog scope.
- backlog-AC2 -> This task. Proof: task provides the executable implementation surface.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_044_alert_on_agent_turns_that_fail_before_completion`
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
