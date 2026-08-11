## task_055_orchestrate_alerts_for_failed_agent_turns - Orchestrate alerts for failed agent turns
> From version: 0.18.4
> Schema version: 1.0
> Status: Done
> Understanding: 85
> Confidence: 80
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: corvus

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
- [x] 1. Confirm that the structured envelope from task_050 has landed and can carry a failure without a new version.
- [x] 2. Provision the Claude failure hook alongside the existing subscriptions, and keep cdx notify silent on stdout as that work established.
- [x] 3. Render transient and actionable failures distinguishably, with wording that cannot read as a completion.
- [x] 4. Add focused tests for each error class, the preview boundary, and mutual exclusion with completion alerts; document the missing Codex equivalent.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_091_alert_on_claude_turns_that_end_in_a_provider_error`

# Definition of Done (DoD)
- [x] Code is implemented and reviewed.
- [x] Validation passes.
- [x] Linked docs are synchronized.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: `StopFailure` is provisioned for Claude and `alert_kind` maps it to its own kind, so one failed turn produces one alert naming the session, the project and the error class. Covered by `test_a_failed_turn_never_reads_as_a_completed_one` (78bfdf4).
- request-AC2 -> This task. Proof: `_failure_state` separates `_TRANSIENT_ERRORS` from the rest and an unrecognised class is treated as needing attention; the title carries ✕ rather than ✓. Covered by `test_a_transient_failure_reads_differently_from_one_needing_action` and `test_an_unknown_error_class_is_treated_as_needing_attention` (78bfdf4).
- request-AC3 -> This task. Proof: `error_message` follows the existing preview preference, normalization and bound, while `error_type` crosses as safe metadata regardless. Covered by `test_a_failure_message_follows_the_preview_opt_in` (78bfdf4).
- request-AC4 -> This task. Proof: `alert_kind` gives each hook event exactly one kind, asserted for all four in `test_each_event_produces_exactly_one_kind`; Stop and StopFailure cannot both describe the same turn because each maps to a single kind (78bfdf4).
- request-AC5 -> This task. Proof: the README states that Codex documents no equivalent hook and that a Codex turn killed by its provider stays silent — a gap in what the provider publishes rather than a setting (78bfdf4).
- request-AC6 -> This task. Proof: 855 Python tests and 77 tray tests pass; ruff, cargo fmt --check and cargo clippy --all-targets are clean on aarch64-apple-darwin, x86_64-pc-windows-msvc and x86_64-unknown-linux-gnu. The tray covers the new kind and its fallback in `a_failed_turn_is_marked_apart_from_both_completion_and_attention` and `an_unknown_kind_falls_back_to_the_neutral_mark` (78bfdf4).
- backlog-AC1 -> This task. Proof: task remains bounded to the linked backlog scope.
- backlog-AC2 -> This task. Proof: task provides the executable implementation surface.

# Validation
- (no validation recorded yet)
- command: `python3 -m pytest (855 passed), ruff, cargo test (77 passed), cargo fmt --check, cargo clippy on the three targets` | result: passed | date: 2026-08-11
- Finish workflow executed on 2026-08-11.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-11.
- Linked backlog item(s): `item_091_alert_on_claude_turns_that_end_in_a_provider_error`
- Related request(s): `req_044_alert_on_agent_turns_that_fail_before_completion`

# Links
- Request: `req_044_alert_on_agent_turns_that_fail_before_completion`
- Product brief(s): (none yet)
- Architecture decision(s): (none yet)
