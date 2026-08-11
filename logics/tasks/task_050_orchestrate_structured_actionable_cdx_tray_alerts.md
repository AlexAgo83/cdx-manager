## task_050_orchestrate_structured_actionable_cdx_tray_alerts - Orchestrate structured actionable CDX tray alerts
> From version: 0.18.4
> Schema version: 1.0
> Status: Done
> Understanding: 95%
> Confidence: 92%
> Progress: 100%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.
> Owner: corvus

# AI Context
- Summary: Orchestrate structured actionable CDX tray alerts
- Keywords: scaffolded-task, request-chain-scaffold, orchestration
- Use when: Coordinating implementation of a scaffolded request chain.
- Skip when: Working on one isolated sibling slice.

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.
- The common contract exists in both providers' published hooks and does not need inventing. Claude Code and Codex both expose `Stop` and `PermissionRequest`, both deliver JSON on stdin, and both carry `session_id`, `transcript_path`, `cwd`, `hook_event_name` and permission_mode.
- `PermissionRequest` carries `tool_name`, tool_input and tool_use_id on both sides; Claude adds permission_category, Codex adds turn_id and `model`. `Stop` carries `last_assistant_message` on both; stop_reason is Claude-only and stop_hook_active is Codex-only, so neither is a contract field.
- Today `src/agent_notify.py:290` provisions Codex on `("Stop", "PermissionRequest")` and `:333` provisions Claude on `("Stop", "Notification")`. That asymmetry is the subject of plan step 3.
- Claude's `Notification` is not only a permission route: notification_type also carries idle_prompt and agent_needs_input, which nothing else reports. Dropping the subscription would lose the "the agent is waiting for you" alert, so the duplicate is removed by filtering notification_type in `cdx notify`, not by unsubscribing.
- Claude's `PermissionRequest` is a decision hook: a non-empty stdout is read as `hookSpecificOutput.decision`. A notification hook that prints anything can allow or deny a tool call, which makes silent exit 0 a correctness property of `cdx notify` rather than a style choice.
- tool_input is where the sensitive content lives — shell command lines, paths, patch bodies — and it stays out of the envelope entirely. Only `tool_name` and permission_category cross the sanitization boundary.
- Claude also publishes StopFailure (error_type, `error_message`), so a turn killed by a rate limit or a billing error is silent today. That gap is tracked separately in req_044 and is out of scope here.

# Plan
- [x] 1. Trace the current hook configuration, payload composition, JSONL spool, Rust parser, notification draw, history, and session action paths; confirm documented provider field availability.
- [x] 2. Define the smallest backward-compatible structured event envelope and pure sanitization boundary, retaining the existing rendered title and message for fallback compatibility. tool_input never enters the envelope.
- [x] 3. Add `PermissionRequest` to Claude provisioning alongside Codex, keep the `Notification` subscription, and remove the duplicate by filtering notification_type to the waiting states in `cdx notify`.
- [x] 4. Render structured completion and permission alert details and wire recent entries to the existing session-launch action without parsing display strings.
- [x] 5. Add focused regression tests for privacy, provider parity, duplicate prevention, compatibility, session actions, and a silent exit 0 on every `PermissionRequest` branch including failures; update concise documentation and run workflow and project validation.
- [x] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [x] Keep commit creation under operator control; do not force one commit per micro-step.
- [x] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`

# Definition of Done (DoD)
- [x] Generated request, product, backlog, and task docs are present.
- [x] Context-pack handoff is available when requested.
- [x] Validation passes.
- [x] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> This task. Proof: `structured_details` in `src/agent_notify.py` builds the envelope and `tray_events.publish` writes it under `details`, beside the existing title and message. `events::Details` in the tray reads it with every field optional. Covered by `test_structured_details_carry_the_safe_fields_and_nothing_else` and `a_structured_permission_alert_names_the_session_and_the_tool` (5702489).
- request-AC2 -> This task. Proof: `events::alert_line` composes from the fields and never parses the sentence; an event without fields is shown as it arrived. Covered by `an_event_without_fields_falls_back_to_the_rendered_sentence` and `a_structured_completion_quotes_its_preview_when_there_is_one` (5702489).
- request-AC3 -> This task. Proof: both providers are provisioned on Stop and PermissionRequest, asserted by `test_both_providers_subscribe_the_same_two_events`; the duplicate is removed by filtering `notification_type` in `cdx notify`, asserted by `test_a_permission_prompt_notification_is_dropped_as_a_duplicate` while `test_the_waiting_notifications_nothing_else_reports_survive` keeps the idle states (5702489).
- request-AC4 -> This task. Proof: `tool_input`, `transcript_path`, `session_id` and `turn_id` never enter the envelope; `test_structured_details_carry_the_safe_fields_and_nothing_else` asserts against the whole serialised blob rather than a field list. The permission description is the single exception the request names and requires the preview opt-in, per `test_a_permission_reason_needs_the_preview_opt_in` (5702489).
- request-AC5 -> This task. Proof: an alert carrying a session renders as `Entry::Action { id: ActionId::Session(name) }`, reusing the launch path task_051 made name-based; one without a session stays text rather than guessing. Covered by `a_structured_alert_opens_the_session_it_names` and `an_alert_without_fields_stays_text_rather_than_guessing` (9c781b3).
- request-AC6 -> This task. Proof: unknown `details` keys are ignored, a non-object `details` degrades to the sentence, and an event without an id is still dropped. Covered by `a_malformed_details_block_leaves_the_sentence_standing` and `an_unknown_event_name_still_produces_a_line` (9c781b3).
- request-AC7 -> This task. Proof: 800 Python tests and 66 tray tests pass; `ruff`, `cargo fmt --check` and `cargo clippy --all-targets` are clean on aarch64-apple-darwin, x86_64-pc-windows-msvc and x86_64-unknown-linux-gnu. `test_a_permission_request_never_writes_to_stdout` covers the decision-silence property on every PermissionRequest path (9c781b3).

# Validation
- (no validation recorded yet)
- command: `python3 -m pytest (800 passed), ruff, cargo test (66 passed), cargo fmt --check, cargo clippy --all-targets on the macOS/Windows/Linux targets` | result: passed | date: 2026-08-11
- Finish workflow executed on 2026-08-11.
- Linked backlog/request close verification passed.

# Report
- Not started.
- Finished on 2026-08-11.
- Linked backlog item(s): `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`
- Related request(s): `req_039_make_cdx_tray_agent_alerts_structured_and_actionable`

# Links
- Request: `req_039_make_cdx_tray_agent_alerts_structured_and_actionable`
- Product brief(s): `prod_028_structured_actionable_tray_agent_alerts`
- Architecture decision(s): (none yet)
