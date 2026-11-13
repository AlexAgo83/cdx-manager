## task_088_implement_protocol_based_remote_messaging_for_interactive_sessions - Implement protocol-based remote messaging for interactive sessions
> From version: 0.26.14
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: Implementation delivery
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: implement, protocol, based, remote, messaging, interactive, sessions
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Context
- Orchestrate the scaffolded request chain and keep sibling implementation slices linked.

# Plan
- [ ] 1. Read provider_runtime launch paths, agent_state and conversation readers; confirm the invariants the feature must not change when disabled.
- [ ] 2. Build the control endpoint, request protocol and cdx send command with owner-only access per platform.
- [ ] 3. Add the Claude local/remote switch loop with queueing, interrupt and event mapping.
- [ ] 4. Add the Codex shared app-server launch and JSON-RPC client with event mapping.
- [ ] 5. Write fake-provider tests, run them on Linux, macOS and Windows, run the live check per platform, and document usage and limits.
- [ ] ADR 009 checkpoint: update affected Logics docs during each meaningful wave and leave the repo commit-ready.
- [ ] Keep commit creation under operator control; do not force one commit per micro-step.
- [ ] GATE: do not close until lint, audit, and scaffold validation pass.

# Backlog
- `item_168_add_a_private_per_session_control_endpoint_and_the_cdx_send_command`
- `item_169_switch_claude_sessions_between_the_tui_and_a_stream_json_resume_run`
- `item_170_share_a_codex_app_server_between_the_tui_and_remote_clients`
- `item_171_prove_the_remote_messaging_loop_on_linux_macos_and_windows`

# Definition of Done (DoD)
- [ ] Generated request, product, backlog, and task docs are present.
- [ ] Context-pack handoff is available when requested.
- [ ] Validation passes.
- [ ] Meaningful waves followed ADR 009: affected docs updated and the repo left commit-ready without automatic commits.

# AC Traceability
- request-AC1 -> `item_168_add_a_private_per_session_control_endpoint_and_the_cdx_send_command`. Proof deferred to slice closeout.
- request-AC5 -> `item_168_add_a_private_per_session_control_endpoint_and_the_cdx_send_command`. Proof deferred to slice closeout.
- request-AC6 -> `item_168_add_a_private_per_session_control_endpoint_and_the_cdx_send_command`. Proof deferred to slice closeout.
- request-AC2 -> `item_169_switch_claude_sessions_between_the_tui_and_a_stream_json_resume_run`. Proof deferred to slice closeout.
- request-AC4 -> `item_169_switch_claude_sessions_between_the_tui_and_a_stream_json_resume_run`. Proof deferred to slice closeout.
- request-AC3 -> `item_170_share_a_codex_app_server_between_the_tui_and_remote_clients`. Proof deferred to slice closeout.
- request-AC4 -> `item_170_share_a_codex_app_server_between_the_tui_and_remote_clients`. Proof deferred to slice closeout.
- request-AC6 -> `item_171_prove_the_remote_messaging_loop_on_linux_macos_and_windows`. Proof deferred to slice closeout.
- request-AC7 -> `item_171_prove_the_remote_messaging_loop_on_linux_macos_and_windows`. Proof deferred to slice closeout.

# Validation
- (no validation recorded yet)

# Report
- Not started.

# Links
- Request: `req_083_protocol_based_remote_messaging_for_interactive_sessions`
- Product brief(s): `prod_058_remote_control_of_interactive_sessions_through_provider_protocols`
- Architecture decision(s): (none yet)

# Executions
| When | Runner | Run id | Title | State | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- |

