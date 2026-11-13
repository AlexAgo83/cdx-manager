## item_168_add_a_private_per_session_control_endpoint_and_the_cdx_send_command - Add a private per-session control endpoint and the cdx send command
> From version: 0.26.14
> Schema version: 1.0
> Status: Ready
> Understanding: 90%
> Confidence: 85%
> Progress: 0%
> Complexity: Medium
> Theme: remote-session-control
> Reminder: Update status/understanding/confidence/progress and linked request/task references when you edit this doc.

# AI Context
- Summary: (unfilled: replace before this doc is used)
- Keywords: add, private, per, session, control, endpoint, cdx, send, command
- Use when: (unfilled: replace before this doc is used)
- Skip when: (unfilled: replace before this doc is used)

# Problem
- Remote clients have no supported way to reach a running interactive session.
- Unix sockets are not available on every Windows setup, and Codex rejects sockets in shared directories.

# Scope
- In:
  - An opt-in launch setting that creates the endpoint for the lifetime of the interactive launcher.
  - A small line-delimited JSON request protocol: send, interrupt, status.
  - `cdx send <session> <text>` and `cdx send --interrupt`, with clear errors when the session is not running or not enabled.
- Out:
  - Remote network exposure.
  - Provider-specific delivery, handled by the next items.

# Acceptance criteria
- AC1: `cdx send` reaches the launcher of a running enabled session and reports delivery or a precise error.
- AC5: The endpoint is owner-only on every platform and never exposes its secret.
- AC6: Disabled sessions launch exactly as before.

# AC Traceability
- request-AC1 -> This backlog slice. Proof: AC1: `cdx send` reaches the launcher of a running enabled session and reports delivery or a precise error.
- request-AC5 -> This backlog slice. Proof: AC5: The endpoint is owner-only on every platform and never exposes its secret.
- request-AC6 -> This backlog slice. Proof: AC6: Disabled sessions launch exactly as before.

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

