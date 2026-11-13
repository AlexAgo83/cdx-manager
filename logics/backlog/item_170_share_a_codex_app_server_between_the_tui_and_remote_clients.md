## item_170_share_a_codex_app_server_between_the_tui_and_remote_clients - Share a Codex app-server between the TUI and remote clients
> From version: 0.26.14
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: High
> Theme: remote-session-control
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: share, codex, app, server, between, tui, remote, clients
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- Codex can serve several clients on one thread, but cdx launches its TUI standalone.

# Scope
- In:
  - Launch `codex app-server` on a private endpoint and the TUI with --remote for enabled sessions, with clean shutdown of both.
  - A minimal JSON-RPC client (initialize, thread/loaded/list, thread/resume, turn/start, turn/interrupt) used by the launcher to deliver messages.
  - Event mapping from turn and item notifications to the event log.
- Out:
  - Approval requests from the app-server beyond the session's configured approval policy.

# Acceptance criteria
- AC3: A message sent with cdx send runs on the TUI's thread and is rendered live in the TUI.
- AC4: The event log records turn states and agent text from notifications.

# AC Traceability
- request-AC3 -> This backlog slice. Proof: AC3: A message sent with cdx send runs on the TUI's thread and is rendered live in the TUI.
- request-AC4 -> This backlog slice. Proof: AC4: The event log records turn states and agent text from notifications.

# Decision framing
- Product framing: Not needed
- Architecture framing: Not needed

# Links
- Product brief(s): `prod_058_remote_control_of_interactive_sessions_through_provider_protocols`
- Architecture decision(s): (none yet)
- Request: `req_083_protocol_based_remote_messaging_for_interactive_sessions`
- Primary task(s): `task_088_implement_protocol_based_remote_messaging_for_interactive_sessions`

# Priority
- Priority: Medium
- Rationale: Set by scaffold input or defaulted for grooming.

# Executions
| When | Runner | Run id | Title | State | PR | Notes |
| --- | --- | --- | --- | --- | --- | --- |

