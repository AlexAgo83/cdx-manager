## task_050_orchestrate_structured_actionable_cdx_tray_alerts - Orchestrate structured actionable CDX tray alerts
> From version: 0.18.4
> Schema version: 1.0
> Status: Ready
> Understanding: 95%
> Confidence: 92%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

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
- [ ] 1. Trace the current hook configuration, payload composition, JSONL spool, Rust parser, notification draw, history, and session action paths; confirm documented provider field availability.
- [ ] 2. Define the smallest backward-compatible structured event envelope and pure sanitization boundary, retaining the existing rendered title and message for fallback compatibility. tool_input never enters the envelope.
- [ ] 3. Add `PermissionRequest` to Claude provisioning alongside Codex, keep the `Notification` subscription, and remove the duplicate by filtering notification_type to the waiting states in `cdx notify`.
- [ ] 4. Render structured completion and permission alert details and wire recent entries to the existing session-launch action without parsing display strings.
- [ ] 5. Add focused regression tests for privacy, provider parity, duplicate prevention, compatibility, session actions, and a silent exit 0 on every `PermissionRequest` branch including failures; update concise documentation and run workflow and project validation.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`. Proof deferred to slice closeout.
- request-AC2 -> `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`. Proof deferred to slice closeout.
- request-AC3 -> `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`. Proof deferred to slice closeout.
- request-AC4 -> `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`. Proof deferred to slice closeout.
- request-AC5 -> `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`. Proof deferred to slice closeout.
- request-AC6 -> `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`. Proof deferred to slice closeout.
- request-AC7 -> `item_086_deliver_structured_private_hook_context_to_actionable_tray_alerts`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_039_make_cdx_tray_agent_alerts_structured_and_actionable`
- Product brief(s): `prod_028_structured_actionable_tray_agent_alerts`
- Architecture decision(s): (none yet)
